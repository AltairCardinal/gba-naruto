#!/usr/bin/env python3
"""Render the GBA background layers of a ``.ss9`` savestate.

Wave 23 / F2 needs the **original** game's ``請準備...`` window pixel-exact.
The window is a **background** layer in the original (the character is drawn on
top of it), so it cannot be cut out of the captured PNG -- it has to be read
out of VRAM.

The savestate carries the whole machine state, so no emulator run is needed:

    VRAM  0x06000000  0x18000 bytes   (char blocks + screen blocks)
    PRAM  0x05000000  0x400  bytes    (16 palettes x 16 colours, RGB555)
    IO    0x04000000  0x400  bytes    (DISPCNT / BGxCNT / BGxHOFS / BGxVOFS)

⚠️ The IO map uses a **2-byte stride**: ``BGxCNT`` = ``0x08 + 2x`` and
``BGxHOFS`` = ``0x10 + 2x``.  Two variants in the repository get this wrong
and this module therefore decodes the IO block itself:

* ``tools/s49_w20e3/bg_registers.py`` reads ``BGxCNT`` with a 4-byte stride
  (it actually reads VCOUNT/BG1CNT/BG3CNT) -- this is AGENTS.md rule 13.
* ``tools/s49_pairing/savestate.py::io_registers`` fixed the ``BGxCNT``
  stride but **still** reads the scroll registers with a 4-byte stride
  (``0x10/0x18/0x20`` instead of ``0x10/0x14/0x18``), so its ``bg_hofs[1]``
  is really ``BG2HOFS`` and its ``bg_hofs[2]`` is not a scroll register at
  all.  Wave 23 / F2 measured this on the original's ``step-20-A.ss9``:
  correct ``BG0HOFS/BG1HOFS/BG2HOFS`` = 240/240/240, the shared reader
  reports 240/240/256.

Usage::

    python tools/s49_w23f2/gba_frame.py --state <a.ss9> --out <dir>
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))

from s49_pairing import savestate  # noqa: E402

IO_BASE = 0x04000000
IO_LENGTH = 0x400
PRAM_BASE = 0x05000000
PRAM_LENGTH = 0x400
VRAM_BASE = 0x06000000
VRAM_LENGTH = 0x18000

SCREEN_W = 240
SCREEN_H = 160

DISPCNT_BG = (0x0001, 0x0002, 0x0004, 0x0008)

# BGxCNT screen size -> (width in tiles, height in tiles).
SCREEN_SIZE_TILES = ((32, 32), (64, 32), (32, 64), (64, 64))


def load(path: pathlib.Path):
    return savestate.load(path)


def io_info(io_bytes: bytes) -> dict:
    """The display registers, read with the correct 2-byte stride.

    Layout (GBA)::

        0x00 DISPCNT  0x04 DISPSTAT  0x06 VCOUNT
        0x08 BG0CNT   0x0A BG1CNT   0x0C BG2CNT   0x0E BG3CNT
        0x10 BG0HOFS  0x12 BG0VOFS
        0x14 BG1HOFS  0x16 BG1VOFS
        0x18 BG2HOFS  0x1A BG2VOFS
        0x1C BG3HOFS  0x1E BG3VOFS
        0x20 BG3X     0x22 BG3Y  (the affine parameters, not scroll)
    """
    import struct

    values = struct.unpack_from("<256H", io_bytes)
    return {
        "dispcnt": values[0x00 // 2],
        "bg_cnt": [values[0x08 // 2 + index] for index in range(4)],
        "bg_hofs": [values[0x10 // 2 + 2 * index] & 0x1FF for index in range(3)],
        "bg_vofs": [values[0x12 // 2 + 2 * index] & 0x1FF for index in range(3)],
        "bg3x": values[0x20 // 2],
        "bg3y": values[0x22 // 2],
        "win_in": values[0x48 // 2] if len(values) > 0x48 // 2 else 0,
        "win_out": values[0x4A // 2] if len(values) > 0x4A // 2 else 0,
    }


def decode_bg(cnt: int) -> dict:
    """One ``BGxCNT`` word."""
    size = (cnt >> 14) & 0x3
    width, height = SCREEN_SIZE_TILES[size]
    return {
        "cnt": cnt,
        "cnt_hex": f"0x{cnt:04X}",
        "char_base_block": (cnt >> 2) & 0x3,
        "mosaic": bool(cnt & 0x40),
        "color_mode_256": bool(cnt & 0x80),
        "screen_base_block": (cnt >> 8) & 0x1F,
        "overflow": bool(cnt & 0x4000),
        "width_tiles": width,
        "height_tiles": height,
        "screen_size": (f"{width * 8}x{height * 8}"),
    }


def _rgb555(value: int) -> tuple[int, int, int]:
    red = value & 0x1F
    green = (value >> 5) & 0x1F
    blue = (value >> 10) & 0x1F
    return ((red << 3) | (red >> 2), (green << 3) | (green >> 2),
            (blue << 3) | (blue >> 2))


def bg_palette(pram: bytes, bank: int) -> list[tuple[int, int, int]]:
    """The 16 colours of one 4bpp background palette bank."""
    base = bank * 32
    out = []
    for index in range(16):
        value = pram[base + index * 2] | (pram[base + index * 2 + 1] << 8)
        out.append(_rgb555(value))
    return out


def bg_palette_256(pram: bytes) -> list[tuple[int, int, int]]:
    """The 256 colours of a 256-colour background (the whole PRAM, in order)."""
    return [_rgb555(pram[index * 2] | (pram[index * 2 + 1] << 8))
            for index in range(256)]


def tile_pixels(vram: bytes, char_base: int, tile_index: int,
                color_mode_256: bool) -> list[list[int]]:
    """One 8x8 tile as 64 colour indices (row major).

    A 4bpp tile is 32 bytes, an 8bpp tile is 64 bytes.
    """
    size = 64 if color_mode_256 else 32
    base = char_base + tile_index * size
    rows = []
    for y in range(8):
        row = []
        for x in range(8):
            if color_mode_256:
                offset = base + y * 8 + x
                row.append(vram[offset] if offset < len(vram) else 0)
            else:
                offset = base + y * 4 + (x >> 1)
                byte = vram[offset] if offset < len(vram) else 0
                row.append((byte >> 4) if (x & 1) == 0 else (byte & 0xF))
        rows.append(row)
    return rows


def tilemap_entries(vram: bytes, bg: dict) -> list[int]:
    """The tilemap of one background as a list of u16 entries."""
    base = bg["screen_base_block"] * 0x800
    count = bg["width_tiles"] * bg["height_tiles"]
    raw = vram[base:base + count * 2]
    entries = []
    for index in range(count):
        entries.append(raw[index * 2] | (raw[index * 2 + 1] << 8))
    return entries


def render_bg(vram: bytes, pram: bytes, bg: dict, hofs: int, vofs: int):
    """Render one background layer as a 240x160 RGB image (PIL)."""
    from PIL import Image

    entries = tilemap_entries(vram, bg)
    char_base = bg["char_base_block"] * 0x10000
    image = Image.new("RGB", (SCREEN_W, SCREEN_H), (0, 0, 0))
    pixels = image.load()
    width_tiles = bg["width_tiles"]
    height_tiles = bg["height_tiles"]
    palette_cache: dict[int, list] = {}

    for screen_y in range(SCREEN_H):
        for screen_x in range(SCREEN_W):
            map_x = (screen_x + hofs) // 8
            map_y = (screen_y + vofs) // 8
            if map_x >= width_tiles:
                map_x = width_tiles - 1
            if map_y >= height_tiles:
                map_y = height_tiles - 1
            entry = entries[map_y * width_tiles + map_x]
            tile = entry & 0x3FF
            hflip = bool(entry & 0x400)
            vflip = bool(entry & 0x800)
            bank = (entry >> 12) & 0xF
            pixel_x = (screen_x + hofs) % 8
            pixel_y = (screen_y + vofs) % 8
            if hflip:
                pixel_x = 7 - pixel_x
            if vflip:
                pixel_y = 7 - pixel_y
            if bg["color_mode_256"]:
                if 256 not in palette_cache:
                    palette_cache[256] = bg_palette_256(pram)
                palette = palette_cache[256]
                index = tile_pixels(vram, char_base, tile, True)[pixel_y][pixel_x]
            else:
                if bank not in palette_cache:
                    palette_cache[bank] = bg_palette(pram, bank)
                palette = palette_cache[bank]
                index = tile_pixels(vram, char_base, tile, False)[pixel_y][pixel_x]
            if index == 0:
                continue  # colour 0 is transparent for a background
            pixels[screen_x, screen_y] = palette[index]
    return image


def render_backgrounds(vram: bytes, pram: bytes, io: dict, force: bool = True) -> dict:
    """Every background layer (rendered even when DISPCNT has it disabled),
    plus the composite.

    ``force`` matters: the original's DISPCNT enables only one background at
    this moment, but the layer that carries the map and the layer that carries
    the ``請準備...`` window must both be identified by comparing each layer's
    pixels with the captured PNG -- so every layer is rendered.
    """
    from PIL import Image

    layers = {}
    composite = Image.new("RGB", (SCREEN_W, SCREEN_H), (0, 0, 0))
    for index in range(4):
        bg = decode_bg(io["bg_cnt"][index])
        bg["index"] = index
        bg["enabled"] = bool(io["dispcnt"] & DISPCNT_BG[index])
        layers[index] = bg
        if not bg["enabled"] and not force:
            continue
        hofs = io["bg_hofs"][index] if index < 3 else 0
        vofs = io["bg_vofs"][index] if index < 3 else 0
        bg["hofs"] = hofs
        bg["vofs"] = vofs
        layer = render_bg(vram, pram, bg, hofs, vofs)
        bg["image"] = layer
        if bg["enabled"]:
            # BG3 has priority over BG2 over BG1 over BG0 in GBA.
            composite = Image.alpha_composite(
                composite.convert("RGBA"), layer.convert("RGBA")).convert("RGB")
    return {"layers": layers, "composite": composite}


def obj_palette(pram: bytes, bank: int) -> list[tuple[int, int, int]]:
    """The 16 colours of one 4bpp object palette bank (PRAM 0x200 + N*32)."""
    base = 0x200 + bank * 32
    out = []
    for index in range(16):
        value = pram[base + index * 2] | (pram[base + index * 2 + 1] << 8)
        out.append(_rgb555(value))
    return out


def obj_palette_256(pram: bytes) -> list[tuple[int, int, int]]:
    """The 128 colours available to an 8bpp object (PRAM 0x200..0x3FF)."""
    return [_rgb555(pram[0x200 + index * 2] | (pram[0x201 + index * 2] << 8))
            for index in range(128)]


# (shape, size) -> (width, height) in pixels.
OBJ_SIZES = {
    (0, 0): (8, 8), (0, 1): (16, 16), (0, 2): (32, 32), (0, 3): (64, 64),
    (1, 0): (16, 8), (1, 1): (32, 16), (1, 2): (32, 32), (1, 3): (64, 32),
}


def render_obj(vram: bytes, pram: bytes, oam: bytes, one_dimensional: bool):
    """Render the object layer as a 240x160 RGB image (PIL).

    The original's battle scene has **no background enabled** (its DISPCNT is
    ``0x1940``: bits 0-3 clear, bit 11 = 1D mapping, bit 12 = OBJ enable), so
    the map, the units *and* the ``請準備...`` window are all objects.
    """
    from PIL import Image

    image = Image.new("RGBA", (SCREEN_W, SCREEN_H), (0, 0, 0, 0))
    pixels = image.load()
    palette_cache: dict[int, list] = {}

    for index in range(128):
        base = index * 8
        attr0 = oam[base] | (oam[base + 1] << 8)
        attr1 = oam[base + 2] | (oam[base + 3] << 8)
        attr2 = oam[base + 4] | (oam[base + 5] << 8)
        if attr0 & 0x0200:      # disabled
            continue
        if attr0 & 0x0100:      # rotation / scaling -- not used by this scene
            continue
        shape = (attr0 >> 14) & 1
        size = (attr1 >> 14) & 3
        width, height = OBJ_SIZES[(shape, size)]
        if attr0 & 0x0400:      # double size (affine only)
            width *= 2
            height *= 2
        color_256 = bool(attr0 & 0x4000)
        bank = (attr2 >> 12) & 0xF
        tile_base = attr2 & 0x3FF
        x = attr1 & 0x1FF
        y = attr0 & 0xFF
        if x >= 240:
            x -= 512
        y -= 16
        if color_256:
            if 256 not in palette_cache:
                palette_cache[256] = obj_palette_256(pram)
            palette = palette_cache[256]
        else:
            if bank not in palette_cache:
                palette_cache[bank] = obj_palette(pram, bank)
            palette = palette_cache[bank]
        tiles_wide = width // 8
        # GBATEK 2D mapping: 16x8 and 32x16 use a 16x8 tile block, every other
        # size uses the 32-wide block.
        tiles_per_row = 16 if (shape == 1 and size in (0, 1)) else 32
        for ty in range(height // 8):
            for tx in range(tiles_wide):
                if one_dimensional:
                    tile = tile_base + ty * tiles_wide + tx
                else:
                    tile = tile_base + ty * tiles_per_row + tx
                pixels_of_tile = tile_pixels(vram, 0x10000, tile, color_256)
                for py in range(8):
                    for px in range(8):
                        index_value = pixels_of_tile[py][px]
                        if index_value == 0:
                            continue
                        screen_x = x + tx * 8 + px
                        screen_y = y + ty * 8 + py
                        if not (0 <= screen_x < SCREEN_W and 0 <= screen_y < SCREEN_H):
                            continue
                        pixels[screen_x, screen_y] = palette[index_value] + (255,)
    return image


def diff_count(left, right) -> int:
    """How many pixels differ between two images of the same size."""
    from PIL import ImageChops

    delta = ImageChops.difference(left.convert("RGB"), right.convert("RGB"))
    red, green, blue = delta.split()
    mask = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    return sum(mask.histogram()[1:])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--png", default="",
                        help="the captured frame to compare each layer with")
    args = parser.parse_args()

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    state = load(pathlib.Path(args.state))
    io = io_info(state.read_memory(IO_BASE, IO_LENGTH))
    pram = state.read_memory(PRAM_BASE, PRAM_LENGTH)
    vram = state.read_memory(VRAM_BASE, VRAM_LENGTH)

    document = {
        "state": str(args.state),
        "dispcnt": io["dispcnt"],
        "dispcnt_hex": f"0x{io['dispcnt']:04X}",
        "bg_cnt": [f"0x{value:04X}" for value in io["bg_cnt"]],
        "bg_hofs": io["bg_hofs"],
        "bg_vofs": io["bg_vofs"],
        "win_in": io["win_in"],
        "win_out": io["win_out"],
    }
    for index in range(4):
        bg = decode_bg(io["bg_cnt"][index])
        bg["enabled"] = bool(io["dispcnt"] & DISPCNT_BG[index])
        document[f"bg{index}"] = bg
    (out / "io.json").write_text(
        json.dumps(document, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8", newline="\n")

    rendered = render_backgrounds(vram, pram, io)
    for index, bg in rendered["layers"].items():
        if "image" in bg:
            bg["image"].save(out / f"bg{index}.png")
    rendered["composite"].save(out / "composite.png")

    oam = state.read_memory(0x07000000, 0x400)
    # DISPCNT bit 4 is the object "character dimension" (0 = 2D, 1 = 1D);
    # bit 11 is "object extended" (affine).  The two are easy to confuse.
    obj = render_obj(vram, pram, oam, bool(io["dispcnt"] & 0x0010))
    obj.save(out / "obj.png")

    if args.png:
        from s49_fidelity_report.pixels import load_rgb

        reference = load_rgb(args.png)
        document["diff_vs_png"] = {}
        for index, bg in rendered["layers"].items():
            if "image" not in bg:
                continue
            count = diff_count(bg["image"], reference)
            document["diff_vs_png"][f"bg{index}"] = count
            print(f"bg{index}: {count} px differ from {args.png}")
        count = diff_count(rendered["composite"], reference)
        document["diff_vs_png"]["composite"] = count
        print(f"composite: {count} px differ from {args.png}")
        count = diff_count(obj.convert("RGB"), reference)
        document["diff_vs_png"]["obj"] = count
        print(f"obj: {count} px differ from {args.png}")
        (out / "io.json").write_text(
            json.dumps(document, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8", newline="\n")

    print(json.dumps(document, ensure_ascii=False, indent=1))
    print("->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
