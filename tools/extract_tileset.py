#!/usr/bin/env python3
"""Extract and export battle map tilesets from the GBA ROM as PNG sheets.

Reads the battle config table at 0x0853D910 (8 entries × 32 bytes),
LZ77-decompresses tile graphics data, and renders tile atlas PNGs.

Usage:
    python tools/extract_tileset.py rom.gba               # all 8 entries
    python tools/extract_tileset.py rom.gba --entry 0     # single entry
    python tools/extract_tileset.py rom.gba --output-dir tiles/
    python tools/extract_tileset.py rom.gba --no-palette  # grayscale only
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

ROM_BASE = 0x08000000

# Battle config table
BATTLE_TABLE_FILE = 0x53D910
BATTLE_TABLE_HEADER = 4       # skip 4 bytes at table base
BATTLE_TABLE_ENTRY_SIZE = 32
BATTLE_TABLE_COUNT = 8

TILES_PER_ROW = 32            # width of PNG atlas in tiles
TILE_PX = 8                   # 8×8 pixels per tile


# ---------------------------------------------------------------------------
# GBA LZ77 decompressor (type 0x10)
# ---------------------------------------------------------------------------

def lz77_decompress(data: bytes, offset: int) -> bytes:
    """Decompress GBA LZ77-encoded data at the given file offset."""
    if data[offset] != 0x10:
        raise ValueError(f"not LZ77 data at 0x{offset:06X}: header byte = 0x{data[offset]:02X}")
    decomp_size = int.from_bytes(data[offset + 1 : offset + 4], "little")
    out = bytearray()
    pos = offset + 4

    while len(out) < decomp_size:
        flags = data[pos]
        pos += 1
        for bit in range(7, -1, -1):
            if len(out) >= decomp_size:
                break
            if flags & (1 << bit):
                # Back-reference: 2 bytes, 1+disp_len bytes copied
                b0 = data[pos]
                b1 = data[pos + 1]
                pos += 2
                disp_len = ((b0 >> 4) & 0xF) + 3
                disp = ((b0 & 0xF) << 8) | b1
                copy_from = len(out) - disp - 1
                for _ in range(disp_len):
                    out.append(out[copy_from])
                    copy_from += 1
            else:
                out.append(data[pos])
                pos += 1

    return bytes(out[:decomp_size])


# ---------------------------------------------------------------------------
# Battle config table reader
# ---------------------------------------------------------------------------

def read_u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def to_file(arm_addr: int) -> int | None:
    if ROM_BASE <= arm_addr < ROM_BASE + 0x800000:
        return arm_addr - ROM_BASE
    return None


def read_battle_entries(data: bytes) -> list[dict]:
    entries = []
    for ch_id in range(BATTLE_TABLE_COUNT):
        base = BATTLE_TABLE_FILE + BATTLE_TABLE_HEADER + ch_id * BATTLE_TABLE_ENTRY_SIZE
        fields = [read_u32(data, base + i * 4) for i in range(8)]
        packed_dims = fields[7]
        width_tiles  = packed_dims & 0xFFFF
        height_tiles = (packed_dims >> 16) & 0xFFFF
        entries.append({
            "chapter_id":      ch_id,
            "file_offset":     base,
            "tile_gfx_ptr":    to_file(fields[0]),
            "tilemap_ptr":     to_file(fields[1]),
            "tilemap_alt_ptr": to_file(fields[2]),
            "extra_ptr":       to_file(fields[3]) if fields[3] != 0 else None,
            "palette_ptr":     to_file(fields[4]),
            "palette2_ptr":    to_file(fields[5]),
            "flags":           fields[6],
            "width_tiles":     width_tiles,
            "height_tiles":    height_tiles,
        })
    return entries


# ---------------------------------------------------------------------------
# Palette helpers
# ---------------------------------------------------------------------------

def bgr555_to_rgb(bgr: int) -> tuple[int, int, int]:
    bgr &= 0x7FFF  # mask off GBA transparency flag (bit 15)
    r5 = bgr & 0x1F
    g5 = (bgr >> 5) & 0x1F
    b5 = (bgr >> 10) & 0x1F
    return (r5 << 3) | (r5 >> 2), (g5 << 3) | (g5 >> 2), (b5 << 3) | (b5 >> 2)


def parse_palette(raw: bytes) -> list[tuple[int, int, int]]:
    """Parse BGR555 palette bytes → list of (R, G, B) tuples."""
    colors = []
    for i in range(0, len(raw), 2):
        bgr = struct.unpack_from("<H", raw, i)[0]
        colors.append(bgr555_to_rgb(bgr))
    return colors


def make_default_palette(n: int = 256) -> list[tuple[int, int, int]]:
    """Grayscale fallback palette."""
    return [(i * 255 // (n - 1),) * 3 for i in range(n)]


# ---------------------------------------------------------------------------
# Tile rendering
# ---------------------------------------------------------------------------

def decode_4bpp_tiles(tile_data: bytes) -> list[list[int]]:
    """Decode 4bpp tile data into a list of tiles, each a 64-element list of palette indices."""
    tiles = []
    num_tiles = len(tile_data) // 32
    for t in range(num_tiles):
        pixels = []
        for byte in tile_data[t * 32 : t * 32 + 32]:
            pixels.append(byte & 0x0F)
            pixels.append((byte >> 4) & 0x0F)
        tiles.append(pixels)
    return tiles


def render_tile_atlas(
    tiles: list[list[int]],
    palette: list[tuple[int, int, int]],
    tiles_per_row: int = TILES_PER_ROW,
    scale: int = 1,
) -> tuple[bytes, int, int]:
    """Render tiles into raw RGB bytes (top-left, row-major).

    Returns (rgb_bytes, width_px, height_px).
    """
    if not tiles:
        return b"", 0, 0

    num_tiles = len(tiles)
    rows = (num_tiles + tiles_per_row - 1) // tiles_per_row
    w_px = tiles_per_row * TILE_PX * scale
    h_px = rows * TILE_PX * scale

    # Flat RGB array
    buf = bytearray(w_px * h_px * 3)

    for tile_idx, pixels in enumerate(tiles):
        tile_col = tile_idx % tiles_per_row
        tile_row = tile_idx // tiles_per_row
        base_x = tile_col * TILE_PX * scale
        base_y = tile_row * TILE_PX * scale

        for py in range(TILE_PX):
            for px in range(TILE_PX):
                color_idx = pixels[py * TILE_PX + px]
                if color_idx < len(palette):
                    r, g, b = palette[color_idx]
                else:
                    r = g = b = 0
                for sy in range(scale):
                    for sx in range(scale):
                        dest_x = base_x + px * scale + sx
                        dest_y = base_y + py * scale + sy
                        i = (dest_y * w_px + dest_x) * 3
                        buf[i] = r
                        buf[i + 1] = g
                        buf[i + 2] = b

    return bytes(buf), w_px, h_px


def write_png(path: Path, rgb_bytes: bytes, width: int, height: int) -> None:
    """Write a minimal PNG file (no external dependencies)."""
    import zlib

    def make_chunk(tag: bytes, data: bytes) -> bytes:
        length = struct.pack(">I", len(data))
        crc = struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return length + tag + data + crc

    # PNG signature
    sig = b"\x89PNG\r\n\x1a\n"

    # IHDR
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit RGB
    ihdr_chunk = make_chunk(b"IHDR", ihdr)

    # IDAT: add filter byte 0 (None) at start of each row
    raw_rows = []
    row_bytes = width * 3
    for y in range(height):
        row = b"\x00" + rgb_bytes[y * row_bytes : (y + 1) * row_bytes]
        raw_rows.append(row)
    compressed = zlib.compress(b"".join(raw_rows), level=6)
    idat_chunk = make_chunk(b"IDAT", compressed)

    # IEND
    iend_chunk = make_chunk(b"IEND", b"")

    path.write_bytes(sig + ihdr_chunk + idat_chunk + iend_chunk)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def extract_entry(
    data: bytes,
    entry: dict,
    output_dir: Path,
    use_palette: bool = True,
    scale: int = 2,
) -> dict:
    """Extract one battle config entry's tileset and write PNG."""
    ch_id = entry["chapter_id"]

    # Decompress tile graphics
    gfx_off = entry["tile_gfx_ptr"]
    if gfx_off is None:
        return {"chapter_id": ch_id, "error": "no tile_gfx_ptr"}

    tile_data = lz77_decompress(data, gfx_off)
    tiles = decode_4bpp_tiles(tile_data)

    # Load palette
    palette: list[tuple[int, int, int]] = make_default_palette(16)
    pal_source = "default_grayscale"

    # Use palette_ptr (fields[4]): LZ77-compressed BG tile palette (16 sub-palettes × 16 colors).
    # Bit 15 in each BGR555 value is the GBA transparency flag; mask it off before converting.
    # palette2_ptr (fields[5]) contains attribute/flag data (all 0x8000), not displayable colors.
    if use_palette and entry["palette_ptr"] is not None:
        try:
            pal_data = lz77_decompress(data, entry["palette_ptr"])
            palette = parse_palette(pal_data)
            pal_source = f"palette_ptr ({len(pal_data)} bytes, {len(palette)} colors)"
        except Exception as e:
            pal_source = f"palette_ptr_error: {e}"

    # Render and write PNG
    rgb_bytes, w_px, h_px = render_tile_atlas(tiles, palette, scale=scale)
    png_path = output_dir / f"battle_tileset_{ch_id:02d}.png"
    output_dir.mkdir(parents=True, exist_ok=True)
    write_png(png_path, rgb_bytes, w_px, h_px)

    return {
        "chapter_id": ch_id,
        "gfx_file_offset": f"0x{gfx_off:06X}",
        "decompressed_size": len(tile_data),
        "num_tiles": len(tiles),
        "palette_source": pal_source,
        "png": str(png_path),
        "dimensions_px": f"{w_px}×{h_px}",
        "map_dims_tiles": f"{entry['width_tiles']}×{entry['height_tiles']}",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract battle map tilesets as PNG atlas sheets.")
    parser.add_argument("rom", type=Path, help="GBA ROM file")
    parser.add_argument("--entry", type=int, default=None, help="Chapter ID (0-7); omit for all")
    parser.add_argument("--output-dir", type=Path, default=Path("build/tiles"), help="Output directory")
    parser.add_argument("--no-palette", action="store_true", help="Use grayscale instead of ROM palette")
    parser.add_argument("--scale", type=int, default=2, help="Pixel scale factor (default 2)")
    args = parser.parse_args()

    if not args.rom.exists():
        print(f"Error: ROM not found: {args.rom}", file=sys.stderr)
        return 1

    data = args.rom.read_bytes()
    entries = read_battle_entries(data)

    if args.entry is not None:
        if args.entry < 0 or args.entry >= BATTLE_TABLE_COUNT:
            print(f"Error: entry must be 0-{BATTLE_TABLE_COUNT - 1}", file=sys.stderr)
            return 1
        targets = [entries[args.entry]]
    else:
        targets = entries

    results = []
    for entry in targets:
        result = extract_entry(data, entry, args.output_dir, not args.no_palette, args.scale)
        results.append(result)
        status = result.get("error", f"{result.get('num_tiles',0)} tiles → {result.get('png','')}")
        print(f"  chapter {result['chapter_id']}: {status}")

    print(f"\nExtracted {len(results)} tileset(s) to {args.output_dir}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
