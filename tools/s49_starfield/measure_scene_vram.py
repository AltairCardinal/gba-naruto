#!/usr/bin/env python3
"""Measure the remake's OBJ VRAM and OAM budget frame by frame.

Why this tool exists
--------------------
Stream Z2 shipped the star black mask as 40 OBJ sprites of 32x32, which is
640 OBJ tiles per level.  The battle screen only has 336 free OBJ tiles, so
the second black field does not fit.  To choose a layout that does fit, the
budget has to be measured *at the black field*, not just somewhere in the
run: the scene's own sprites are alive while the mask is up, and they take
both OBJ tiles and OAM entries.

This tool replays the remake's opening (the same key schedule the project's
black field capture uses) and samples, after every single GBA frame:

  * the sprite tile allocator's own ``free_tiles_count`` counter (the only
    correct measure of free OBJ tiles: the allocator is sparse, so the high
    water mark of the tile region is not free space),
  * the whole OAM (128 entries x 8 bytes) to count the sprites in use,
  * the background palette RAM to spot the black field: the black field is a
    palette fade, so the palette darkens while it runs.

Usage::

    python tools/s49_starfield/measure_scene_vram.py \
        --rom "D:\\...\\butano-sequel.gba" \
        --out build/s49-starfield/scene-vram.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import struct
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
VICTORY = REPO / "tools" / "s49_victory_capture"
if str(VICTORY) not in sys.path:
    sys.path.insert(0, str(VICTORY))

import probe as probe_module  # noqa: E402

VRAM = 0x06000000
# The OAM is *not* in VRAM: it is the separate 1 KiB object attribute memory
# at 0x07000000 (0x06000000 is the background character data).  Reading the
# sprite list from the wrong address silently returns the background tiles.
OAM = 0x07000000
OAM_SIZE = 0x400
PALETTE = 0x05000000
PALETTE_SIZE = 0x200

DEFAULT_EXE = REPO / "build" / "mgba-probe-w2" / "mgba-probe.exe"

# Butano's sprite tile allocator keeps its bookkeeping in one EWRAM buffer.
# The buffer's address comes from the linked ELF:
#
#   arm-none-eabi-nm -C butano-sequel.elf | grep sprite_tiles_manager
#       -> 02029a38 b bn::sprite_tiles_manager::(anonymous namespace)::data_buffer
#
# and the offset of ``free_tiles_count`` inside it comes from the literal
# pool of ``_allocate_impl`` (5740).
SPRITE_TILES_MANAGER_ADDRESS = 0x02029A38
FREE_TILES_COUNT_OFFSET = 5740
OBJ_TILE_COUNT = 1024

# The opening: the deployment screen is reached with two Down presses and the
# battle starts with A (the project's black field capture uses this schedule).
KEYS = ["Down", "Down"] + ["A"] * 22
ZERO_FRAMES = 240
SETTLE_FRAMES = 90
HOLD_FRAMES = 4


def decode_oam(data: bytes) -> list[dict]:
    """The OAM entries that hold a sprite.

    Butano parks the OAM entries of the sprites it does not use with
    ``attr0 == 0x0200`` (the affine "disable" encoding), so those entries are
    not counted.
    """
    sprites = []
    for index in range(128):
        offset = index * 8
        attr0, attr1, attr2 = struct.unpack_from("<HHH", data, offset)
        if attr0 == 0x0200 and attr1 == 0 and attr2 == 0:
            continue
        if attr0 == 0 and attr1 == 0 and attr2 == 0:
            continue
        sprites.append({
            "index": index,
            "attr0": attr0,
            "x": attr1 & 0x1FF,
            "y": attr0 & 0x1FF,
            "size_bits": (attr1 >> 14) & 3,
            "tile": attr2 & 0x3FF,
            "priority": (attr2 >> 14) & 3,
        })
    return sprites


def palette_sum(data: bytes) -> int:
    """The total brightness of the background palettes."""
    total = 0
    for index in range(0, len(data) - 1, 2):
        total += data[index] | (data[index + 1] << 8)
    return total


def fade_regions(sums: list[int]) -> list[tuple[int, int]]:
    """The frame ranges where the palette is being faded.

    The black field is a palette fade, so the palette's total brightness
    changes from frame to frame while it runs.  A scene change replaces the
    whole palette at once, so only the *ramp* frames count.
    """
    regions = []
    start = None
    for index in range(1, len(sums)):
        if sums[index] != sums[index - 1]:
            if start is None:
                start = index - 1
        elif start is not None:
            regions.append((start, index - 1))
            start = None
    if start is not None:
        regions.append((start, len(sums) - 1))
    return regions


def run_schedule(probe, addr: int, length: int, prefix: str, scratch: pathlib.Path):
    """Replay the opening and dump ``length`` bytes after every frame.

    Returns the dump files in frame order.  The same schedule is replayed for
    every region, so the frame numbers line up.
    """
    files = []
    scratch.mkdir(parents=True, exist_ok=True)
    mask_down = probe_module.key_mask(["Down"])
    mask_a = probe_module.key_mask(["A"])

    def dump(count: int, mask: int, tag: str) -> None:
        base = str(scratch / (tag + "_" + prefix))
        probe.framedump(count, addr, length, mask, base)
        for index in range(count):
            files.append(pathlib.Path(f"{base}-{index:04d}.bin"))

    dump(ZERO_FRAMES, 0, "zero")
    for index, key in enumerate(KEYS):
        mask = mask_down if key == "Down" else mask_a
        dump(HOLD_FRAMES, mask, f"key{index:02d}")
        dump(SETTLE_FRAMES, 0, f"gap{index:02d}")
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=pathlib.Path, required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    parser.add_argument("--scratch", type=pathlib.Path,
                        default=REPO / "build" / "mgba-probe-w2" / "dumps")
    parser.add_argument("--manager-address", type=lambda v: int(v, 0),
                        default=SPRITE_TILES_MANAGER_ADDRESS)
    parser.add_argument("--free-count-offset", type=lambda v: int(v, 0),
                        default=FREE_TILES_COUNT_OFFSET)
    args = parser.parse_args(argv)

    scratch = args.scratch
    counter_address = args.manager_address + args.free_count_offset

    with probe_module.Probe(args.rom, exe=args.exe) as probe:
        # The palettes: the black field is a palette fade.
        palette_files = run_schedule(probe, PALETTE, PALETTE_SIZE, "pal",
                                     scratch)
        # The allocator's own free tile counter.
        counter_files = run_schedule(probe, counter_address, 2, "cnt", scratch)
        # The whole OAM.
        oam_files = run_schedule(probe, OAM, OAM_SIZE, "oam", scratch)

    if not (len(palette_files) == len(counter_files) == len(oam_files)):
        raise SystemExit("dump counts differ between the runs")

    samples = []
    for index in range(len(palette_files)):
        palette = palette_files[index].read_bytes()
        counter = counter_files[index].read_bytes()
        oam = oam_files[index].read_bytes()
        free = counter[0] | (counter[1] << 8)
        sprites = decode_oam(oam)
        samples.append({
            "frame": index,
            "palette_sum": palette_sum(palette),
            "obj_tiles_free": free,
            "obj_tiles_used": OBJ_TILE_COUNT - free,
            "sprites": len(sprites),
            "sprite_priorities": sorted({sprite["priority"]
                                         for sprite in sprites}),
        })

    regions = fade_regions([sample["palette_sum"] for sample in samples])
    black_frames = []
    for first, last in regions:
        black_frames.extend(range(first, last + 1))
    black_frames = sorted(set(black_frames))
    worst_tiles = min(samples, key=lambda sample: sample["obj_tiles_free"])
    worst_sprites = max(samples, key=lambda sample: sample["sprites"])
    field_tiles = min((samples[frame]["obj_tiles_free"]
                       for frame in black_frames), default=None)
    field_sprites = max((samples[frame]["sprites"]
                          for frame in black_frames), default=None)
    field_used = max((samples[frame]["obj_tiles_used"]
                      for frame in black_frames), default=None)

    report = {
        "schema": "konoha.s49-star-scene-vram.v2",
        "rom": str(args.rom),
        "rom_sha256": hashlib.sha256(args.rom.read_bytes()).hexdigest(),
        "manager_address": hex(args.manager_address),
        "free_count_offset": args.free_count_offset,
        "oam_address": hex(OAM),
        "frames_sampled": len(samples),
        "free_tiles_at_frame_0": samples[0]["obj_tiles_free"],
        "fade_regions": regions,
        "black_field_frame_count": len(black_frames),
        "worst_free_obj_tiles": worst_tiles,
        "worst_sprite_count": worst_sprites,
        "black_field_min_free_obj_tiles": field_tiles,
        "black_field_max_used_obj_tiles": field_used,
        "black_field_max_sprites": field_sprites,
        "samples": samples,
    }
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8",
                   newline="\n")

    print("frames sampled:", len(samples))
    print("free tiles at frame 0:", samples[0]["obj_tiles_free"])
    print("fade regions (the black field):", regions)
    print("black field: min free obj tiles:", field_tiles,
          " max used:", field_used, " max sprites:", field_sprites)
    print("worst free obj tiles over the whole run:", worst_tiles)
    print("worst sprite count over the whole run:", worst_sprites)
    print("->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
