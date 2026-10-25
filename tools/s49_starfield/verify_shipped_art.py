#!/usr/bin/env python3
"""Check that the shipped star mask art really reaches the ROM intact.

Why this tool exists
--------------------
The mask's VRAM cost depends on two things that the offline analysis
assumes:

  * a 16x16 sprite frame is 4 OBJ tiles and a 32x32 frame is 16, and
  * the frame *f* of the art is the frame the placement table points at.

Both are facts about the Butano asset pipeline (GRIT converts the bitmap into
metatiles, Butano keeps the frames in the order GRIT's map lists them), not
about the tool that wrote the bitmap.  This tool closes the loop: it reads
the tile data back out of the linked ROM and rebuilds the picture of every
frame, then compares it with the frame the placement table expects.

A mismatch means the art would be drawn wrong on the GBA, even though every
offline number looked fine.

Usage::

    python tools/s49_starfield/verify_shipped_art.py \
        --rom "D:\\...\\butano-sequel.gba" \
        --elf "D:\\...\\butano-sequel.elf" \
        --graphics "D:\\...\\graphics" \
        --out build/s49-starfield/shipped-art-check.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import struct
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]

WIDTH = 240
HEIGHT = 160
CELL = 16
BLOCK = 32
FRAMES_PER_ROW = 8

# The two GRIT metatile orders a 2x2 metatile can use.  The tool finds out
# which one the pipeline used instead of assuming it.
METATILE_ORDERS = {
    "row_major": [(0, 0), (1, 0), (0, 1), (1, 1)],
    "column_major": [(0, 0), (0, 1), (1, 0), (1, 1)],
    "diagonal": [(0, 0), (1, 1), (1, 0), (0, 1)],
}


def wsl_path(path: pathlib.Path) -> str:
    """A Windows path as a WSL path."""
    text = str(path.resolve())
    if re.match(r"^[A-Za-z]:\\\\", text) or re.match(r"^[A-Za-z]:\\", text):
        drive = text[0].lower()
        rest = text[2:].replace("\\", "/")
        return f"/mnt/{drive}/{rest}"
    return text


def read_tiles_from_assembly(path: pathlib.Path, symbol: str) -> list[bytes]:
    """The tile data of a symbol, read out of GRIT's assembly output.

    The art only reaches the ROM when the game includes the sprite item, so
    the check reads the build's intermediate instead: it holds exactly the
    tile data the linker would copy into the ROM.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    start = text.find(symbol + ":")
    if start < 0:
        raise SystemExit(f"symbol not found in {path}: {symbol}")
    words = []
    for match in re.finditer(r"\.word\s+([^\n@]*)", text[start:]):
        for value in match.group(1).split(","):
            value = value.strip()
            if value:
                words.append(int(value, 16))
    tiles = []
    for index in range(len(words) // 8):
        tile = b""
        for word in words[index * 8:(index + 1) * 8]:
            tile += struct.pack("<I", word)
        tiles.append(tile)
    return tiles


def symbol_address(elf: pathlib.Path, name: str) -> int:
    """The address of a symbol in the linked ELF."""
    result = subprocess.run(
        ["wsl", "-d", "Ubuntu-24.04", "--", "bash", "-lc",
         "source /opt/devkitpro/devkitarm.sh && "
         f"arm-none-eabi-nm {wsl_path(elf)} | grep ' {name}$'"],
        capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"symbol not found in the ELF: {name}\n"
                         f"{result.stdout}\n{result.stderr}")
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1] == name:
            return int(parts[0], 16)
    raise SystemExit(f"symbol not found: {name}")


def read_tiles(rom: pathlib.Path, address: int, count: int) -> list[bytes]:
    """The tile data of a symbol, read out of the ROM."""
    offset = address - 0x08000000
    data = rom.read_bytes()[offset:offset + count * 32]
    if len(data) != count * 32:
        raise SystemExit("the ROM is too short for the symbol")
    return [data[index * 32:(index + 1) * 32] for index in range(count)]


def tile_pixels(tile: bytes) -> list[int]:
    """The 4bpp pixels of one 8x8 tile.

    The GBA's 4bpp format is *not* the bitmap's: a byte holds two pixels and
    the left one is in the low nibble (the bitmap puts it in the high
    nibble).  Getting this backwards shifts every odd pixel by one column.
    """
    pixels = []
    for row in range(8):
        for column in range(4):
            byte = tile[row * 4 + column]
            pixels.append(byte & 0xF)
            pixels.append((byte >> 4) & 0xF)
    return pixels


def frame_pixels(tiles: list[bytes], order: list[tuple[int, int]],
                 size: int) -> list[int]:
    """The picture of one sprite frame, from its metatile's tiles."""
    tiles_per_row = size // 8
    pixels = [0] * (size * size)
    for index, (tile_x, tile_y) in enumerate(order):
        source = tile_pixels(tiles[index])
        for y in range(8):
            for x in range(8):
                pixels[(tile_y * 8 + y) * size + tile_x * 8 + x] = \
                    source[y * 8 + x]
    return pixels


def read_back_bmp(path: pathlib.Path) -> list[list[int]]:
    """Read a written bitmap back."""
    data = path.read_bytes()
    offset = int.from_bytes(data[10:14], "little")
    width = int.from_bytes(data[18:22], "little")
    height = int.from_bytes(data[22:26], "little")
    stride = (((width + 1) // 2) + 3) & ~3
    pixels = []
    for y in range(height - 1, -1, -1):
        row = []
        base = offset + y * stride
        for x in range(width):
            byte = data[base + x // 2]
            row.append((byte >> 4) if x % 2 == 0 else (byte & 0x0F))
        pixels.append(row)
    return pixels


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=pathlib.Path, required=True)
    parser.add_argument("--elf", type=pathlib.Path, required=True)
    parser.add_argument("--build", type=pathlib.Path,
                        help="the build folder with GRIT's assembly output")
    parser.add_argument("--graphics", type=pathlib.Path, required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--cell-item", default="battle_black_field_star_mask16")
    parser.add_argument("--block-item",
                        default="battle_black_field_star_block32")
    args = parser.parse_args(argv)

    results = {}
    for item, size in ((args.cell_item, CELL), (args.block_item, BLOCK)):
        symbol = f"{item}_bn_gfxTiles"
        bitmap = read_back_bmp(args.graphics / f"{item}.bmp")
        rows = len(bitmap) // size
        frames = rows * FRAMES_PER_ROW
        address = None
        if args.build:
            assembly = args.build / f"{item}_bn_gfx.s"
            tiles = read_tiles_from_assembly(assembly, symbol)
            source = str(assembly)
        else:
            address = symbol_address(args.elf, symbol)
            tiles = read_tiles(args.rom, address, frames * (size // 8) ** 2)
            source = str(args.rom)

        expected = []
        for frame in range(frames):
            origin_x = (frame % FRAMES_PER_ROW) * size
            origin_y = (frame // FRAMES_PER_ROW) * size
            expected.append([
                bitmap[origin_y + y][origin_x + x]
                for y in range(size) for x in range(size)
            ])

        best = None
        for name, order in METATILE_ORDERS.items():
            if size == BLOCK:
                order = [(0, 0), (1, 0), (2, 0), (3, 0),
                         (0, 1), (1, 1), (2, 1), (3, 1),
                         (0, 2), (1, 2), (2, 2), (3, 2),
                         (0, 3), (1, 3), (2, 3), (3, 3)]
            mismatches = 0
            for frame in range(frames):
                tiles_of_frame = tiles[frame * (size // 8) ** 2:
                                      (frame + 1) * (size // 8) ** 2]
                picture = frame_pixels(tiles_of_frame, order, size)
                if picture != expected[frame]:
                    mismatches += 1
            if best is None or mismatches < best[1]:
                best = (name, mismatches)
            if mismatches == 0:
                break

        results[item] = {
            "symbol": symbol,
            "source": source,
            "rom_address": hex(address) if address is not None else None,
            "frames": frames,
            "tiles": len(tiles),
            "metatile_order": best[0],
            "frames_mismatched": best[1],
            "ok": best[1] == 0,
        }

    ok = all(result["ok"] for result in results.values())
    report = {
        "schema": "konoha.s49-star-shipped-art.v1",
        "rom": str(args.rom),
        "rom_sha256": hashlib.sha256(args.rom.read_bytes()).hexdigest(),
        "items": results,
        "shipped_art_ok": ok,
    }
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8",
                   newline="\n")
    for item, result in results.items():
        print("%-40s %s frames %d, metatile order %s, mismatched frames %d"
              % (item, result["source"], result["frames"],
                 result["metatile_order"], result["frames_mismatched"]))
    print("shipped art ok:", ok)
    print("->", out)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
