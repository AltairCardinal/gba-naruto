#!/usr/bin/env python3
"""Export battle-map and story-background tilesets from the GBA ROM as PNG atlases.

Everything below was verified on ``rom/base.gba``
(SHA-1 26f60795fa5e63b4f0264b84e453beffd56b9f7d) by decompressing the LZ77
blocks and checking the resulting lengths against the table's own dimensions.

Battle scenario table -- file ``0x53D910``, 8 entries x 32 bytes
-----------------------------------------------------------------
===== ========= ====================================================
Off   Type     Meaning
===== ========= ====================================================
+0x00 u16      raw width   (``>> 2`` = cells wide)
+0x02 u16      raw height  (``>> 1`` = cells tall)
+0x04 u32 ptr  tile graphics, LZ77, 4bpp (32 bytes per tile)
+0x08 u32 ptr  palette, LZ77, 192 x BGR555 (12 banks x 16 colours)
+0x0C u32 ptr  layer 0, LZ77, metatile-index planes (2 x cells u16)
+0x10 u32 ptr  layer 1, LZ77, metatile-index planes (0 when absent)
+0x14 u32 ptr  metatile table, LZ77, 8 bytes per metatile
+0x18 u32 ptr  terrain table, LZ77, one u16 per cell
+0x1C u8       story background id
===== ========= ====================================================

Story background table -- file ``0x59903C``, 16 bytes per id
-----------------------------------------------------------
===== ========= ====================================================
+0x00 u32 ptr  tile graphics, LZ77 (4bpp, or 8bpp when flag bit0 set)
+0x04 u32 ptr  palette, LZ77, 192 x BGR555
+0x08 u32 ptr  tilemap, LZ77, u16 GBA tilemap entries
+0x0C u32      flags, bit0 = 8bpp graphics
===== ========= ====================================================

The native loader (ROM ``0x08088348``) turns one entry into a **full 32x32
GBA background map**:

* graphics  -> VRAM ``0x06000000 + charblock * 0x4000``;
* palette   -> VRAM ``0x05000000`` (BG palette RAM, bank 0, 192 colours);
* tilemap   -> VRAM ``0x06000000 + screenblock * 0x800``;
* the rest of that 2 KB screen block is filled with a constant tile by
  ``CpuFastSet`` (``svc 0x0C``) at ``0x080883B0`` / ``0x080883CC``:
  ``0x00000000`` (tile 0) for 4bpp entries and ``0x001E001E`` (tile 30)
  for 8bpp entries.  320 real entries + 704 filler = 1024 = 32 x 32.

Only the top 10 rows carry the entry's own tilemap; rows 10..31 (and the
visible 30 x 20 screen) are the filler tile.

Tile descriptors (used by the metatile table) follow the GBA layout:
bits 0-9 tile number, bit 10 horizontal flip, bit 11 vertical flip,
bits 12-15 palette bank.

Usage:
    python tools/extract_tileset.py rom/base.gba
    python tools/extract_tileset.py rom/base.gba --kind battle
    python tools/extract_tileset.py rom/base.gba --entry 0
    python tools/extract_tileset.py rom/base.gba --output-dir build/tiles
    python tools/extract_tileset.py rom/base.gba --scale 3 --no-palette
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.lib.io import write_text  # noqa: E402

ROM_BASE = 0x08000000

# Battle scenario table
BATTLE_TABLE_FILE = 0x53D910
BATTLE_TABLE_COUNT = 8
BATTLE_ENTRY_SIZE = 32

# Story background table
STORY_TABLE_FILE = 0x59903C
STORY_ENTRY_SIZE = 16
STORY_ENTRY_COUNT = 16

TILE_PX = 8
METATILE_PX = TILE_PX * 2
TILES_PER_ROW = 32
METATILES_PER_ROW = 16
PALETTE_COLORS = 192          # 12 banks x 16 colours
BANK_SIZE = 16

# Native story-background geometry (ROM 0x08088348):
#   the loader writes one 32x32 GBA background map per entry; the entry's own
#   LZ77 tilemap supplies the first rows, the rest is a constant filler tile.
STORY_MAP_COLS = 32
STORY_MAP_ROWS = 32
STORY_MAP_ENTRIES = STORY_MAP_COLS * STORY_MAP_ROWS
# filler tile written by CpuFastSet, keyed by the entry's bpp
STORY_FILLER = {4: 0x0000, 8: 0x001E}


# ---------------------------------------------------------------------------
# GBA LZ77 decompressor (type 0x10)
# ---------------------------------------------------------------------------

def lz77_decompress(data: bytes, offset: int) -> bytes:
    """Decompress GBA LZ77-encoded data at the given file offset."""
    if offset < 0 or offset + 4 > len(data):
        raise ValueError(f"LZ77 offset 0x{offset:06X} outside ROM")
    if data[offset] != 0x10:
        raise ValueError(f"not LZ77 data at 0x{offset:06X}: header byte = 0x{data[offset]:02X}")
    decomp_size = int.from_bytes(data[offset + 1:offset + 4], "little")
    out = bytearray()
    pos = offset + 4

    while len(out) < decomp_size:
        flags = data[pos]
        pos += 1
        for bit in range(7, -1, -1):
            if len(out) >= decomp_size:
                break
            if flags & (1 << bit):
                # Back-reference: 2 bytes, 3..18 bytes copied
                b0 = data[pos]
                b1 = data[pos + 1]
                pos += 2
                disp_len = ((b0 >> 4) & 0xF) + 3
                disp = ((b0 & 0xF) << 8) | b1
                copy_from = len(out) - disp - 1
                if copy_from < 0:
                    raise ValueError(f"bad LZ77 back-reference at 0x{offset:06X}")
                for _ in range(disp_len):
                    out.append(out[copy_from])
                    copy_from += 1
            else:
                out.append(data[pos])
                pos += 1

    return bytes(out[:decomp_size])


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def read_u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def read_u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def to_file(arm_addr: int) -> int | None:
    if ROM_BASE <= arm_addr < ROM_BASE + 0x800000:
        return arm_addr - ROM_BASE
    return None


def bgr555_to_rgb(bgr: int) -> tuple[int, int, int]:
    """Convert one BGR555 value (bit 15 = transparency flag) to 8-bit RGB."""
    bgr &= 0x7FFF
    r5 = bgr & 0x1F
    g5 = (bgr >> 5) & 0x1F
    b5 = (bgr >> 10) & 0x1F
    return (r5 << 3) | (r5 >> 2), (g5 << 3) | (g5 >> 2), (b5 << 3) | (b5 >> 2)


def parse_palette(raw: bytes) -> list[tuple[int, int, int]]:
    """Parse BGR555 palette bytes -> list of (R, G, B), 16 entries per bank."""
    colors = []
    for i in range(0, len(raw) - 1, 2):
        colors.append(bgr555_to_rgb(struct.unpack_from("<H", raw, i)[0]))
    return colors


def make_default_palette(n: int = PALETTE_COLORS) -> list[tuple[int, int, int]]:
    """Grayscale fallback palette."""
    if n < 2:
        return [(0, 0, 0)]
    return [(i * 255 // (n - 1),) * 3 for i in range(n)]


# ---------------------------------------------------------------------------
# Tile decoding
# ---------------------------------------------------------------------------

def decode_tiles(tile_data: bytes, bpp: int = 4) -> list[list[int]]:
    """Decode tile data into a list of tiles, each a list of palette indices.

    GBA 4bpp tiles hold 8 rows of 4 bytes; every byte carries two pixels and
    the *lower* nibble is the left pixel.  8bpp tiles hold one byte per pixel.
    """
    if bpp == 4:
        size = 32
    elif bpp == 8:
        size = 64
    else:
        raise ValueError(f"unsupported bpp {bpp}")
    tiles = []
    for t in range(len(tile_data) // size):
        chunk = tile_data[t * size:(t + 1) * size]
        pixels: list[int] = []
        if bpp == 4:
            for byte in chunk:
                pixels.append(byte & 0x0F)
                pixels.append((byte >> 4) & 0x0F)
        else:
            pixels.extend(chunk)
        tiles.append(pixels)
    return tiles


def apply_flip(pixels: list[int], width: int, height: int,
               h_flip: bool, v_flip: bool) -> list[int]:
    """Return a copy of ``pixels`` with optional horizontal/vertical mirroring."""
    if not h_flip and not v_flip:
        return pixels
    flipped = list(pixels)
    if h_flip:
        for row in range(height):
            base = row * width
            flipped[base:base + width] = reversed(flipped[base:base + width])
    if v_flip:
        rows = [flipped[row * width:(row + 1) * width] for row in range(height)]
        rows.reverse()
        flipped = [px for row in rows for px in row]
    return flipped


# ---------------------------------------------------------------------------
# PNG output (no third-party dependency)
# ---------------------------------------------------------------------------

def write_png(path: Path, rgb_bytes: bytes, width: int, height: int) -> None:
    """Write a minimal 8-bit RGB PNG file."""
    def make_chunk(tag: bytes, payload: bytes) -> bytes:
        length = struct.pack(">I", len(payload))
        crc = struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        return length + tag + payload + crc

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row_bytes = width * 3
    raw_rows = bytearray()
    for y in range(height):
        raw_rows += b"\x00"
        raw_rows += rgb_bytes[y * row_bytes:(y + 1) * row_bytes]
    idat = make_chunk(b"IDAT", zlib.compress(bytes(raw_rows), level=6))
    path.write_bytes(sig + make_chunk(b"IHDR", ihdr) + idat + make_chunk(b"IEND", b""))


class Canvas:
    """Tiny RGB canvas with nearest-neighbour scaled drawing."""

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.buf = bytearray(width * height * 3)

    def put(self, x: int, y: int, rgb: tuple[int, int, int]) -> None:
        if not (0 <= x < self.width and 0 <= y < self.height):
            return
        i = (y * self.width + x) * 3
        self.buf[i] = rgb[0]
        self.buf[i + 1] = rgb[1]
        self.buf[i + 2] = rgb[2]

    def blit(self, x: int, y: int, pixels: list[int], width: int, height: int,
             palette: list[tuple[int, int, int]], scale: int) -> None:
        for py in range(height):
            for px in range(width):
                color_idx = pixels[py * width + px]
                rgb = palette[color_idx] if color_idx < len(palette) else (0, 0, 0)
                for sy in range(scale):
                    for sx in range(scale):
                        self.put(x + px * scale + sx, y + py * scale + sy, rgb)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        write_png(path, bytes(self.buf), self.width, self.height)


def bank_color(palette: list[tuple[int, int, int]], bank: int, index: int) -> tuple[int, int, int]:
    """Look up a colour inside a 16-colour palette bank."""
    flat = bank * BANK_SIZE + index
    if 0 <= flat < len(palette):
        return palette[flat]
    return (0, 0, 0)


# ---------------------------------------------------------------------------
# Battle scenario table
# ---------------------------------------------------------------------------

def read_battle_entries(data: bytes) -> list[dict]:
    entries = []
    for ch_id in range(BATTLE_TABLE_COUNT):
        base = BATTLE_TABLE_FILE + ch_id * BATTLE_ENTRY_SIZE
        raw_width = read_u16(data, base)
        raw_height = read_u16(data, base + 2)
        fields = [read_u32(data, base + 4 + i * 4) for i in range(6)]
        entries.append({
            "chapter_id": ch_id,
            "file_offset": base,
            "raw_width": raw_width,
            "raw_height": raw_height,
            "width_cells": raw_width >> 2,
            "height_cells": raw_height >> 1,
            "tile_gfx_ptr": to_file(fields[0]),
            "palette_ptr": to_file(fields[1]),
            "layer0_ptr": to_file(fields[2]),
            "layer1_ptr": to_file(fields[3]),
            "metatile_ptr": to_file(fields[4]),
            "terrain_ptr": to_file(fields[5]),
            "background_id": data[base + 28],
        })
    return entries


def split_planes(blob: bytes, cells: int) -> list[list[int]]:
    """Split a decompressed layer block into one u16 index list per plane."""
    values = list(struct.unpack_from(f"<{len(blob) // 2}H", blob))
    if cells <= 0:
        return [values]
    planes = []
    rest = values
    while rest:
        planes.append(rest[:cells])
        rest = rest[cells:]
    return planes


def render_tile_atlas(tiles: list[list[int]], palette: list[tuple[int, int, int]],
                       bank: int, scale: int, per_row: int = TILES_PER_ROW) -> Canvas:
    rows = max(1, (len(tiles) + per_row - 1) // per_row)
    canvas = Canvas(per_row * TILE_PX * scale, rows * TILE_PX * scale)
    flat = [bank_color(palette, bank, i) for i in range(BANK_SIZE)]
    for index, pixels in enumerate(tiles):
        col = index % per_row
        row = index // per_row
        canvas.blit(col * TILE_PX * scale, row * TILE_PX * scale,
                    pixels, TILE_PX, TILE_PX, flat, scale)
    return canvas


def render_metatile_atlas(metatiles: list[list[tuple[int, int, int, int]]],
                          tiles: list[list[int]],
                          palette: list[tuple[int, int, int]],
                          scale: int, per_row: int = METATILES_PER_ROW) -> Canvas:
    """Render every metatile (2x2 tiles) with its own palette bank and flips."""
    rows = max(1, (len(metatiles) + per_row - 1) // per_row)
    canvas = Canvas(per_row * METATILE_PX * scale, rows * METATILE_PX * scale)
    for index, descriptors in enumerate(metatiles):
        col = index % per_row
        row = index // per_row
        ox = col * METATILE_PX * scale
        oy = row * METATILE_PX * scale
        for slot, (tile_id, h_flip, v_flip, bank) in enumerate(descriptors):
            if tile_id >= len(tiles):
                continue
            pixels = apply_flip(tiles[tile_id], TILE_PX, TILE_PX, h_flip, v_flip)
            flat = [bank_color(palette, bank, i) for i in range(BANK_SIZE)]
            tx = ox + (slot % 2) * TILE_PX * scale
            ty = oy + (slot // 2) * TILE_PX * scale
            canvas.blit(tx, ty, pixels, TILE_PX, TILE_PX, flat, scale)
    return canvas


def render_map(plane: list[int], metatiles: list[list[tuple[int, int, int, int]]],
               tiles: list[list[int]], palette: list[tuple[int, int, int]],
               width_cells: int, height_cells: int, scale: int) -> Canvas:
    """Render one metatile-index plane as a map image."""
    canvas = Canvas(width_cells * METATILE_PX * scale, height_cells * METATILE_PX * scale)
    for y in range(height_cells):
        for x in range(width_cells):
            cell = y * width_cells + x
            if cell >= len(plane):
                continue
            meta_id = plane[cell]
            if meta_id >= len(metatiles):
                continue
            descriptors = metatiles[meta_id]
            ox = x * METATILE_PX * scale
            oy = y * METATILE_PX * scale
            for slot, (tile_id, h_flip, v_flip, bank) in enumerate(descriptors):
                if tile_id >= len(tiles):
                    continue
                pixels = apply_flip(tiles[tile_id], TILE_PX, TILE_PX, h_flip, v_flip)
                flat = [bank_color(palette, bank, i) for i in range(BANK_SIZE)]
                tx = ox + (slot % 2) * TILE_PX * scale
                ty = oy + (slot // 2) * TILE_PX * scale
                canvas.blit(tx, ty, pixels, TILE_PX, TILE_PX, flat, scale)
    return canvas


def parse_metatiles(blob: bytes) -> list[list[tuple[int, int, int, int]]]:
    """Parse the metatile table: 8 bytes per entry = 4 GBA tile descriptors."""
    metatiles = []
    for i in range(len(blob) // 8):
        entry = []
        for slot in range(4):
            value = struct.unpack_from("<H", blob, i * 8 + slot * 2)[0]
            entry.append((value & 0x3FF, bool(value & 0x400), bool(value & 0x800),
                          (value >> 12) & 0xF))
        metatiles.append(entry)
    return metatiles


def extract_battle_entry(data: bytes, entry: dict, output_dir: Path,
                          use_palette: bool, scale: int) -> dict:
    ch_id = entry["chapter_id"]
    result: dict = {
        "chapter_id": ch_id,
        "table_offset": entry["file_offset"],
        "raw_width": entry["raw_width"],
        "raw_height": entry["raw_height"],
        "cells": f"{entry['width_cells']}x{entry['height_cells']}",
        "background_id": entry["background_id"],
    }

    if entry["tile_gfx_ptr"] is None:
        result["error"] = "missing tile graphics pointer"
        return result

    gfx = lz77_decompress(data, entry["tile_gfx_ptr"])
    tiles = decode_tiles(gfx, 4)
    result["tile_count"] = len(tiles)
    result["tile_gfx_offset"] = f"0x{entry['tile_gfx_ptr']:06X}"

    palette = make_default_palette()
    if use_palette and entry["palette_ptr"] is not None:
        pal_blob = lz77_decompress(data, entry["palette_ptr"])
        palette = parse_palette(pal_blob)
        result["palette_offset"] = f"0x{entry['palette_ptr']:06X}"
        result["palette_colors"] = len(palette)
    else:
        result["palette_source"] = "grayscale fallback"

    # --- tile atlas --------------------------------------------------------
    atlas = render_tile_atlas(tiles, palette, 0, scale)
    atlas_path = output_dir / f"battle_{ch_id:02d}_tiles.png"
    atlas.save(atlas_path)
    result["tiles_png"] = str(atlas_path)
    result["tiles_png_size"] = f"{atlas.width}x{atlas.height}"

    # --- metatiles ---------------------------------------------------------
    metatiles: list[list[tuple[int, int, int, int]]] = []
    if entry["metatile_ptr"] is not None:
        meta_blob = lz77_decompress(data, entry["metatile_ptr"])
        metatiles = parse_metatiles(meta_blob)
        result["metatile_count"] = len(metatiles)
        result["metatile_offset"] = f"0x{entry['metatile_ptr']:06X}"
        result["metatile_flipped_tiles"] = sum(
            1 for m in metatiles for d in m if d[1] or d[2])
        meta_canvas = render_metatile_atlas(metatiles, tiles, palette, scale)
        meta_path = output_dir / f"battle_{ch_id:02d}_metatiles.png"
        meta_canvas.save(meta_path)
        result["metatiles_png"] = str(meta_path)

    # --- map planes --------------------------------------------------------
    planes: list[tuple[str, list[int]]] = []
    cells = entry["width_cells"] * entry["height_cells"]
    if entry["layer0_ptr"] is not None:
        blob = lz77_decompress(data, entry["layer0_ptr"])
        for i, plane in enumerate(split_planes(blob, cells)):
            planes.append((f"layer0_{i}", plane))
    if entry["layer1_ptr"] is not None:
        blob = lz77_decompress(data, entry["layer1_ptr"])
        for i, plane in enumerate(split_planes(blob, cells)):
            planes.append((f"layer1_{i}", plane))

    result["planes"] = []
    for name, plane in planes:
        canvas = render_map(plane, metatiles, tiles, palette,
                            entry["width_cells"], entry["height_cells"], scale)
        path = output_dir / f"battle_{ch_id:02d}_map_{name}.png"
        canvas.save(path)
        result["planes"].append({
            "name": name,
            "entries": len(plane),
            "min": min(plane) if plane else None,
            "max": max(plane) if plane else None,
            "png": str(path),
        })

    # --- terrain -----------------------------------------------------------
    if entry["terrain_ptr"] is not None:
        terrain = lz77_decompress(data, entry["terrain_ptr"])
        result["terrain_offset"] = f"0x{entry['terrain_ptr']:06X}"
        result["terrain_cells"] = len(terrain) // 2
        result["terrain_distinct"] = len(set(struct.unpack_from(f"<{len(terrain) // 2}H", terrain)))
    return result


# ---------------------------------------------------------------------------
# Story background table
# ---------------------------------------------------------------------------

def read_story_entries(data: bytes) -> list[dict]:
    entries = []
    for bg_id in range(STORY_ENTRY_COUNT):
        base = STORY_TABLE_FILE + bg_id * STORY_ENTRY_SIZE
        gfx, pal, tilemap, flags = struct.unpack_from("<IIII", data, base)
        bpp = 8 if flags & 1 else 4
        # The table has 16 slots but only 0..13 are real entries: slot 8 is
        # empty, and slots 14/15 hold the head of a *different* table (their
        # flags word is not 0/1).  The native loader only ever distinguishes
        # 4bpp from 8bpp through the flags byte, so flags must be 0 or 1.
        valid = (flags in (0, 1)
                 and to_file(gfx) is not None
                 and to_file(pal) is not None
                 and to_file(tilemap) is not None)
        entries.append({
            "background_id": bg_id,
            "file_offset": base,
            "gfx_ptr": to_file(gfx),
            "palette_ptr": to_file(pal),
            "tilemap_ptr": to_file(tilemap),
            "flags": flags,
            "bpp": bpp,
            "valid": valid,
            "filler_tile": STORY_FILLER[bpp],
        })
    return entries


def extract_story_entry(data: bytes, entry: dict, output_dir: Path,
                        use_palette: bool, scale: int) -> dict:
    bg_id = entry["background_id"]
    result: dict = {
        "background_id": bg_id,
        "table_offset": entry["file_offset"],
        "bpp": entry["bpp"],
        "flags": entry["flags"],
    }
    if not entry.get("valid", True):
        result["error"] = (f"not a story background entry "
                           f"(flags=0x{entry['flags']:08X})")
        return result
    if entry["gfx_ptr"] is None:
        result["error"] = "empty entry"
        return result

    gfx = lz77_decompress(data, entry["gfx_ptr"])
    tiles = decode_tiles(gfx, entry["bpp"])
    result["tile_count"] = len(tiles)
    result["gfx_offset"] = f"0x{entry['gfx_ptr']:06X}"

    palette = make_default_palette()
    if use_palette and entry["palette_ptr"] is not None:
        palette = parse_palette(lz77_decompress(data, entry["palette_ptr"]))
        result["palette_colors"] = len(palette)

    atlas = render_tile_atlas(tiles, palette, 0, scale)
    atlas_path = output_dir / f"story_{bg_id:02d}_tiles.png"
    atlas.save(atlas_path)
    result["tiles_png"] = str(atlas_path)

    if entry["tilemap_ptr"] is not None:
        blob = lz77_decompress(data, entry["tilemap_ptr"])
        count = len(blob) // 2
        values = list(struct.unpack_from(f"<{count}H", blob))
        # Native layout: the entry's tilemap fills the top of a 32x32 GBA
        # background map; CpuFastSet writes the remaining entries with one
        # constant filler tile (0 for 4bpp, 0x1E for 8bpp).
        filler = entry["filler_tile"]
        entries_total = max(count, STORY_MAP_ENTRIES)
        values += [filler] * (entries_total - count)
        width = STORY_MAP_COLS
        height = (entries_total + width - 1) // width
        result["tilemap_entries"] = count
        result["filler_entries"] = entries_total - count
        result["filler_tile"] = f"0x{filler:04X}"
        canvas = Canvas(width * TILE_PX * scale, height * TILE_PX * scale)
        for i, value in enumerate(values):
            tile_id = value & 0x3FF
            h_flip = bool(value & 0x400)
            v_flip = bool(value & 0x800)
            bank = (value >> 12) & 0xF
            if tile_id >= len(tiles):
                continue
            pixels = apply_flip(tiles[tile_id], TILE_PX, TILE_PX, h_flip, v_flip)
            flat = [bank_color(palette, bank, k) for k in range(BANK_SIZE)]
            canvas.blit((i % width) * TILE_PX * scale, (i // width) * TILE_PX * scale,
                        pixels, TILE_PX, TILE_PX, flat, scale)
        map_path = output_dir / f"story_{bg_id:02d}_map.png"
        canvas.save(map_path)
        result["map_png"] = str(map_path)
        result["map_grid"] = f"{width}x{height}"
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract battle map and story background tilesets as PNG atlases.")
    parser.add_argument("rom", type=Path, help="GBA ROM file")
    parser.add_argument("--kind", choices=("battle", "story", "both"), default="both")
    parser.add_argument("--entry", type=int, default=None,
                        help="battle chapter id (0-7) or story background id")
    parser.add_argument("--output-dir", type=Path, default=Path("build/tiles"))
    parser.add_argument("--no-palette", action="store_true",
                        help="Use grayscale instead of the ROM palettes")
    parser.add_argument("--scale", type=int, default=2, help="Pixel scale factor (default 2)")
    parser.add_argument("--manifest", type=Path, default=None,
                        help="Write a JSON manifest (default: <output-dir>/manifest.json)")
    args = parser.parse_args()

    if not args.rom.exists():
        print(f"Error: ROM not found: {args.rom}", file=sys.stderr)
        return 1
    if args.scale < 1:
        print("Error: --scale must be >= 1", file=sys.stderr)
        return 1

    data = args.rom.read_bytes()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    use_palette = not args.no_palette

    manifest: dict = {
        "rom": str(args.rom),
        "rom_size": len(data),
        "battle_table": f"0x{BATTLE_TABLE_FILE:06X}",
        "story_table": f"0x{STORY_TABLE_FILE:06X}",
        "scale": args.scale,
        "battle": [],
        "story": [],
    }

    if args.kind in ("battle", "both"):
        entries = read_battle_entries(data)
        targets = entries
        if args.entry is not None:
            if not 0 <= args.entry < BATTLE_TABLE_COUNT:
                print(f"Error: --entry must be 0-{BATTLE_TABLE_COUNT - 1} for --kind battle",
                      file=sys.stderr)
                return 1
            targets = [entries[args.entry]]
        for entry in targets:
            result = extract_battle_entry(data, entry, args.output_dir, use_palette, args.scale)
            manifest["battle"].append(result)
            if "error" in result:
                print(f"  battle {result['chapter_id']}: {result['error']}")
            else:
                planes = ", ".join(p["name"] for p in result.get("planes", []))
                print(f"  battle {result['chapter_id']}: {result['tile_count']} tiles, "
                      f"{result.get('metatile_count', 0)} metatiles, "
                      f"cells {result['cells']}, planes [{planes}] -> "
                      f"{result['tiles_png']}")

    if args.kind in ("story", "both") and args.entry is None:
        for entry in read_story_entries(data):
            result = extract_story_entry(data, entry, args.output_dir, use_palette, args.scale)
            if "error" in result:
                continue
            manifest["story"].append(result)
            print(f"  story {result['background_id']}: {result['tile_count']} tiles "
                  f"({result['bpp']}bpp), tilemap {result.get('tilemap_entries', 0)} entries "
                  f"-> {result['tiles_png']}")

    manifest_path = args.manifest or (args.output_dir / "manifest.json")
    write_text(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(f"\nManifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
