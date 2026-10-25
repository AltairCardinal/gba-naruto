#!/usr/bin/env python3
"""Measure the remake's VRAM headroom where the 「開始」 title has to fit.

Why this tool exists
--------------------
Stream Y2 did not put the title art into the remake's graphics/ directory
because it did not know whether the VRAM could take it.  This tool answers
that question with numbers instead of guesses.

The GBA's VRAM (96 KiB) is laid out like this on the remake (Butano):

    0x06000000 - 0x0600FFFF   64 KiB  background character (tile) data
    0x06010000 - 0x06017FFF   32 KiB  object character (tile) data
                                (1024 4bpp tiles)

The title art is an OBJ sprite item, so it lives in the object tile region.
The tool replays the remake's opening (the same key schedule the project's
black field capture uses), dumps the whole VRAM every few frames and reports
the object tile region's occupancy, so the free space can be compared with
the title's cost.

Usage::

    python tools/s49_opening_title/measure_vram_headroom.py \
        --rom "D:\\...\\butano-sequel.gba" \
        --out build/s49-opening-title/vram-headroom.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
VICTORY = REPO / "tools" / "s49_victory_capture"
if str(VICTORY) not in sys.path:
    sys.path.insert(0, str(VICTORY))

import probe as probe_module  # noqa: E402

VRAM = 0x06000000
VRAM_SIZE = 0x18000
BG_TILE_REGION = (0x00000, 0x10000)
OBJ_TILE_REGION = (0x10000, 0x18000)
OBJ_TILE_COUNT = 1024
TILE_BYTES = 32

DEFAULT_EXE = REPO / "build" / "mgba-probe-z2" / "mgba-probe.exe"

# Butano's sprite tile allocator keeps its bookkeeping in one EWRAM buffer.
# The buffer's address and the offset of ``free_tiles_count`` inside it come
# from the linked ELF:
#
#   arm-none-eabi-nm -C butano-sequel.elf | grep sprite_tiles_manager
#       -> 02029a38 b bn::sprite_tiles_manager::(anonymous namespace)::data_buffer
#   arm-none-eabi-objdump -d butano-sequel.elf   (the literal pool of
#   _allocate_impl holds the member offsets: 5740 = free_tiles_count)
#
# The high water mark of the object tile region is NOT a free space
# measurement: Butano's best fit allocator spreads the allocations over the
# whole region, so the last byte is almost always in use while most of the
# region is free.  The allocator's own counter is the number that matters.
SPRITE_TILES_MANAGER_ADDRESS = 0x02029A38
FREE_TILES_COUNT_OFFSET = 5740
OBJ_TILE_COUNT = 1024

# The remake's opening: the deployment screen is reached with two Down presses
# and the battle starts with A (the project's black field capture uses this
# schedule).
KEYS = ["Down", "Down"] + ["A"] * 22
ZERO_FRAMES = 240
SETTLE_FRAMES = 90
HOLD_FRAMES = 4


def region_stats(data: bytes, start: int, end: int) -> dict:
    block = data[start:end]
    nonzero = sum(1 for byte in block if byte)
    high_water = len(block)
    while high_water > 0 and block[high_water - 1] == 0:
        high_water -= 1
    return {
        "size": len(block),
        "nonzero_bytes": nonzero,
        "high_water_bytes": high_water,
        "free_bytes_at_high_water": len(block) - high_water,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=pathlib.Path, required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    parser.add_argument("--sample-every", type=int, default=10)
    parser.add_argument("--manager-address", type=lambda v: int(v, 0),
                        default=SPRITE_TILES_MANAGER_ADDRESS)
    parser.add_argument("--free-count-offset", type=lambda v: int(v, 0),
                        default=FREE_TILES_COUNT_OFFSET)
    args = parser.parse_args(argv)

    mask_down = probe_module.key_mask(["Down"])
    mask_a = probe_module.key_mask(["A"])

    samples = []
    with probe_module.Probe(args.rom, exe=args.exe) as probe:
        probe.frames(ZERO_FRAMES, 0)
        frame = ZERO_FRAMES
        for index, key in enumerate(KEYS):
            mask = mask_down if key == "Down" else mask_a
            probe.frames(HOLD_FRAMES, mask)
            frame += HOLD_FRAMES
            probe.frames(SETTLE_FRAMES, 0)
            frame += SETTLE_FRAMES
            if index % 2 == 0 or index < 4:
                data = probe.dump(VRAM, VRAM_SIZE)
                obj = region_stats(data, *OBJ_TILE_REGION)
                bg = region_stats(data, *BG_TILE_REGION)
                counter = probe.dump(args.manager_address +
                                     args.free_count_offset, 2)
                free_tiles = counter[0] | (counter[1] << 8)
                samples.append({
                    "frame": frame,
                    "key_index": index,
                    "key": key,
                    "obj_tile_region": obj,
                    "bg_tile_region": bg,
                    "obj_tiles_free": free_tiles,
                    "obj_tiles_used": OBJ_TILE_COUNT - free_tiles,
                })
        final_shot = pathlib.Path(args.out).with_suffix(".png")
        probe.shot(str(final_shot))

    peak = max(samples, key=lambda row: row["obj_tiles_used"])
    worst_free = min(samples, key=lambda row: row["obj_tiles_free"])
    report = {
        "schema": "konoha.s49-opening-title-vram-headroom.v1",
        "rom": str(args.rom),
        "rom_sha256": hashlib.sha256(args.rom.read_bytes()).hexdigest(),
        "obj_tile_region": {
            "vram_start": "0x06010000",
            "vram_end": "0x06017FFF",
            "bytes": OBJ_TILE_REGION[1] - OBJ_TILE_REGION[0],
            "tiles_4bpp": OBJ_TILE_COUNT,
            "tile_bytes": TILE_BYTES,
        },
        "peak_obj_usage": peak,
        "worst_free_obj_tiles": worst_free,
        "samples": samples,
        "final_screenshot": str(final_shot),
    }
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8", newline="\n")
    for row in samples:
        print("frame %5d key %-4s obj tiles used %4d / %d  free %4d   "
              "(bg region high water %6d)"
              % (row["frame"], row["key"], row["obj_tiles_used"],
                 OBJ_TILE_COUNT, row["obj_tiles_free"],
                 row["bg_tile_region"]["high_water_bytes"]))
    print("peak:", json.dumps(peak, ensure_ascii=False))
    print("->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
