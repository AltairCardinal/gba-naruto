#!/usr/bin/env python3
"""Decode the original game's BG layers out of a captured VRAM dump.

The S49 capture in ``build/s49-rule/capture`` holds a full 0x18000 byte VRAM
dump per overlay moment.  This script renders the map layer (BG1) and the
overlay layer (BG2) of one such dump as PNGs, so the two layers can be related
to each other in *map space*.

GBA I/O offsets used here (relative to 0x04000000)::

    0x00 DISPCNT   0x0C BGCNT2   0x14 BG1HOFS   0x18 BG2HOFS
    0x08 BGCNT0    0x10 BG0HOFS  0x16 BG1VOFS   0x1A BG2VOFS
"""

from __future__ import annotations

import argparse
import pathlib
import struct

from PIL import Image

VRAM_BASE = 0x06000000
SCREEN_W = 240
SCREEN_H = 160


def read_io(path: pathlib.Path) -> dict[str, int]:
    data = path.read_bytes()
    names = {
        "DISPCNT": 0x00, "BGCNT0": 0x08, "BGCNT1": 0x0A,
        "BGCNT2": 0x0C, "BGCNT3": 0x0E,
        "BG0HOFS": 0x10, "BG0VOFS": 0x12,
        "BG1HOFS": 0x14, "BG1VOFS": 0x16,
        "BG2HOFS": 0x18, "BG2VOFS": 0x1A,
        "BG3HOFS": 0x1C, "BG3VOFS": 0x1E,
    }
    out = {}
    for name, off in names.items():
        out[name] = data[off] | (data[off + 1] << 8)
    return out


def bg_layout(bgcnt: int) -> dict[str, int]:
    return {
        "charbase": ((bgcnt >> 2) & 3) * 0x4000,
        "screenbase": ((bgcnt >> 8) & 0x1F) * 0x400,
        "bpp": 4 if (bgcnt >> 13) & 1 else 8,
        "size": (bgcnt >> 14) & 3,
        "priority": bgcnt & 3,
    }


def decode_tile_8bpp(vram: bytes, tile: int) -> list[list[int]]:
    base = tile * 64
    rows = []
    for y in range(8):
        start = base + y * 8
        rows.append(list(vram[start:start + 8]))
    return rows


def vram_palette(vram: bytes, bpp: int, bank: int) -> list[tuple[int, int, int]]:
    """The BG palette `bank` as RGB8.

    8bpp: 16 palettes of 16 entries live at VRAM 0x000..0x1FF.
    4bpp: 16 palettes of 4 entries live at VRAM 0x000..0x0FF
          (bank stride 0x20 bytes = 8 entries of 2 bytes).
    """
    out = []
    if bpp == 4:
        base = bank * 0x20
        for i in range(16):
            value = vram[base + i * 2] | (vram[base + i * 2 + 1] << 8)
            out.append(_rgb8(value))
    else:
        base = bank * 0x200
        for i in range(256):
            value = vram[base + i * 2] | (vram[base + i * 2 + 1] << 8)
            out.append(_rgb8(value))
    return out


def _rgb8(value: int) -> tuple[int, int, int]:
    r = value & 0x1F
    g = (value >> 5) & 0x1F
    b = (value >> 10) & 0x1F
    return ((r << 3) | (r >> 2), (g << 3) | (g >> 2), (b << 3) | (b >> 2))


def decode_tile_4bpp(vram: bytes, tile: int) -> list[list[int]]:
    base = tile * 32
    rows = []
    for y in range(8):
        start = base + y * 4
        row = []
        for byte in vram[start:start + 4]:
            row.append(byte & 0x0F)
            row.append((byte >> 4) & 0x0F)
        rows.append(row)
    return rows


def render_layer(vram: bytes, bgcnt: int, bank: int = 0,
                 ) -> tuple[Image.Image, list[list[int]]]:
    layout = bg_layout(bgcnt)
    palette = vram_palette(vram, layout["bpp"], bank)
    columns = 32 if layout["size"] in (0, 2) else 64
    rows = 32 if layout["size"] in (0, 1) else 64
    screenbase = layout["charbase"] + layout["screenbase"]
    entries = struct.unpack_from(f"<{columns * rows}H", vram, screenbase)
    image = Image.new("RGB", (columns * 8, rows * 8))
    pixels = image.load()
    tile_cache: dict[int, list[list[int]]] = {}
    for index, entry in enumerate(entries):
        tile = entry & 0x03FF
        hflip = (entry >> 10) & 1
        vflip = (entry >> 11) & 1
        entry_bank = (entry >> 12) & 0x0F
        if tile not in tile_cache:
            if layout["bpp"] == 4:
                tile_cache[tile] = decode_tile_4bpp(vram, tile)
            else:
                tile_cache[tile] = decode_tile_8bpp(vram, tile)
        art = tile_cache[tile]
        cell_x = (index % columns) * 8
        cell_y = (index // columns) * 8
        for y in range(8):
            src_row = art[7 - y] if vflip else art[y]
            for x in range(8):
                src_x = 7 - x if hflip else x
                value = src_row[src_x]
                if layout["bpp"] == 4:
                    colour = palette[entry_bank * 16 + value]
                else:
                    colour = palette[value]
                pixels[cell_x + x, cell_y + y] = colour
    return image, entries


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--capture-dir", type=pathlib.Path, required=True)
    ap.add_argument("--moment", default="field-frame-v1")
    ap.add_argument("--out-dir", type=pathlib.Path, required=True)
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    vram = (args.capture_dir / f"{args.moment}.vram-0000.bin").read_bytes()
    io = read_io(args.capture_dir / f"{args.moment}.io-0000.bin")
    print(f"=== {args.moment} ===")
    for name in ("DISPCNT", "BGCNT0", "BGCNT1", "BGCNT2", "BGCNT3",
                 "BG1HOFS", "BG1VOFS", "BG2HOFS", "BG2VOFS"):
        value = io[name]
        extra = ""
        if name.startswith("BGCNT"):
            layout = bg_layout(value)
            extra = (f"  prio={layout['priority']} charbase=0x{layout['charbase']:05X}"
                     f" screenbase=0x{layout['screenbase']:05X}"
                     f" bpp={layout['bpp']} size={layout['size']}")
        print(f"  {name:<8} 0x{value:04X}{extra}")

    # bank 12 palette (16 entries) from the overlay layer
    palette_data = pathlib.Path(
        r"D:\Shell\Github\gba-naruto-butano\artifacts"
        r"\s49-original-movegrid-tilemap-v1\bg2-palette.bin")
    palette = []
    if palette_data.is_file():
        raw = palette_data.read_bytes()
        for i in range(16):
            value = raw[i * 2] | (raw[i * 2 + 1] << 8)
            r = (value & 0x1F)
            g = (value >> 5) & 0x1F
            b = (value >> 10) & 0x1F
            palette.append(((r << 3) | (r >> 2), (g << 3) | (g >> 2),
                            (b << 3) | (b >> 2)))
    else:
        palette = [(0, 0, 0)] * 16
    print(f"  bank12 palette: {palette}")

    for name, bgcnt_key, bank in (("bg1", "BGCNT1", 0), ("bg2", "BGCNT2", 12)):
        image, entries = render_layer(vram, io[bgcnt_key], bank)
        out = args.out_dir / f"{args.moment}.{name}.png"
        image.save(out)
        distinct = sorted({entry & 0x3FF for entry in entries})
        print(f"  wrote {out}  ({image.width}x{image.height})  "
              f"distinct tiles: {len(distinct)}  first: {distinct[:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
