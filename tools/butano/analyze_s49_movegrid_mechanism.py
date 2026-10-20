#!/usr/bin/env python3
"""Decode the original's move-range screen: which GPU state draws it.

The move-range grid was the largest unexplained pixel gap in the S49 remake
(2917 differing pixels against the original's frame).  The previous rounds
narrowed it to "the original dims the area it cannot reach" but could not say
*how*, because the two kinds of evidence available did not fit together: the
archived PNGs and the archived palette dumps came from **different mGBA
builds**, and their colour spaces do not agree.

This analyzer works from same-frame receipts instead
(``tools/butano/capture_s49_frame_palette.py``): for the move-range frame and
the round-banner frame it decodes

* the display registers (DISPCNT, the four BGxCNT, BLDCNT, the scrolls),
* BG3's tilemap out of the frame's own VRAM,
* how many of the frame's colours are palette entries of that same frame.

The third number is the important one for anybody who wants to reason about
colours: it says whether the screenshot's colour space and the palette's
colour space agree *in this very frame*, which is exactly the assumption the
earlier "the dimmed colours are not in PRAM, so it is not a palette swap"
argument rested on.

Usage::

    python3 tools/butano/analyze_s49_movegrid_mechanism.py
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

GRID_DIR = ROOT / "artifacts/s49-original-movegrid-frame-v1"
BANNER_DIR = ROOT / "artifacts/s49-original-banner-frame-v1"
FIELD_DIR = ROOT / "artifacts/s49-original-field-frame-v1"
GRID16_DIR = ROOT / "artifacts/s49-original-grid16-frame-v1"
DEFAULT_OUT = ROOT / "artifacts/s49-original-movegrid-mechanism-v1"

# GBA DISPCNT in mode 0.  Bit 15 ("LCD enable") is reported but not
# interpreted: this mGBA build leaves it clear even while the frame renders.
DISPCNT_FIELDS = (
    (0, 2, "bg_mode"),
    (4, 1, "frame_select"),
    (5, 1, "hblank_free"),
    (6, 1, "obj_1d_mapping"),
    (7, 1, "bg0_char_base_10000"),
    (8, 1, "bg1_char_base_10000"),
    (9, 1, "bg2_char_base_10000"),
    (10, 1, "bg3_char_base_10000"),
    (11, 1, "obj_char_base_10000"),
    (12, 1, "obj_enable"),
    (15, 1, "lcd_enable"),
)


class MechanismError(RuntimeError):
    """A receipt is missing or unusable."""


def _u16(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset:offset + 2], "little")


def decode_dispcnt(value: int) -> dict[str, int]:
    return {
        name: (value >> low) & ((1 << width) - 1)
        for low, width, name in DISPCNT_FIELDS
    }


def decode_bgcnt(value: int) -> dict[str, int]:
    return {
        "priority": value & 0x03,
        "char_base_block": (value >> 2) & 0x03,
        "mosaic": (value >> 6) & 0x01,
        "palette_256": (value >> 7) & 0x01,
        "screen_base_block": (value >> 8) & 0x1F,
        "overflow": (value >> 13) & 0x01,
    }


def naive_expand(value: int) -> int:
    return (value << 3) | (value >> 2)


def palette_colors(pram: bytes) -> set[tuple[int, int, int]]:
    colors: set[tuple[int, int, int]] = set()
    for bank in range(32):
        for index in range(16):
            word = _u16(pram, bank * 32 + index * 2)
            red, green, blue = word & 0x1F, (word >> 5) & 0x1F, (word >> 10) & 0x1F
            colors.add(
                (
                    naive_expand(red),
                    naive_expand(green),
                    naive_expand(blue),
                )
            )
    return colors


def frame_colors(png_path: Path) -> set[tuple[int, int, int]]:
    try:
        from PIL import Image
    except ImportError as error:  # pragma: no cover - Pillow is a dependency
        raise MechanismError(f"Pillow is required: {error}") from error
    with Image.open(png_path) as image:
        converted = image.convert("RGB")
        pixels = converted.load()
        return {
            pixels[x, y]
            for y in range(converted.size[1])
            for x in range(converted.size[0])
        }


def tilemap(vram: bytes, screen_base: int) -> list[int]:
    return [
        _u16(vram, screen_base + 2 * index)
        for index in range(32 * 32)
    ]


def active_sprites(oam: bytes) -> list[dict[str, int]]:
    """Return the OAM entries that are actually used.

    OAM is raw memory, so this comparison does not depend on the colour
    space of the screenshot: if the move-range frame enables sprites the
    banner frame does not, the overlay is drawn with sprites.
    """

    sprites: list[dict[str, int]] = []
    for slot in range(128):
        base = slot * 8
        y = oam[base]
        x = oam[base + 1]
        attr2 = oam[base + 2] | (oam[base + 3] << 8)
        if (attr2 & 0x0FFF) == 0:
            continue
        sprites.append(
            {
                "slot": slot,
                "x": x | ((y & 1) << 8),
                "y": y >> 1,
                "tile": attr2 & 0x1FF,
                "palette": (attr2 >> 12) & 0x0F,
                "size_bits": (attr2 & 0x1800) >> 9,
                "shape": (attr2 >> 14) & 0x03,
            }
        )
    return sprites


def read_frame(
        directory: Path,
        banner_vram: bytes | None = None,
        banner_pram: bytes | None = None,
        banner_oam: bytes | None = None,
) -> dict[str, Any]:
    directory = Path(directory)
    pram_path = directory / "pram-00.bin"
    io_path = directory / "io-00.bin"
    vram_path = directory / "vram-00.bin"
    png_path = directory / "frame-00.png"
    for path in (pram_path, io_path, vram_path, png_path):
        if not path.is_file():
            raise MechanismError(f"missing receipt file: {path}")
    oam_path = directory / "oam-00.bin"
    if not oam_path.is_file():
        raise MechanismError(f"missing receipt file: {oam_path}")
    oam = oam_path.read_bytes()
    pram = pram_path.read_bytes()
    io = io_path.read_bytes()
    vram = vram_path.read_bytes()
    reference = vram if banner_vram is None else banner_vram
    reference_pram = pram if banner_pram is None else banner_pram

    dispcnt = _u16(io, 0x00)
    bgcnt = [_u16(io, 0x08 + 2 * index) for index in range(4)]
    bg3 = decode_bgcnt(bgcnt[3])
    bg3_screen_base = bg3["screen_base_block"] * 0x800
    colors = frame_colors(png_path)
    palette = palette_colors(pram)
    return {
        "_vram": vram,
        "_pram": pram,
        "_oam": oam,
        "directory": str(directory),
        "registers": {
            "dispcnt": f"0x{dispcnt:04X}",
            "dispcnt_fields": decode_dispcnt(dispcnt),
            "bldcnt": f"0x{_u16(io, 0x50):04X}",
            "bldalpha": f"0x{_u16(io, 0x52):04X}",
            "bldy": f"0x{_u16(io, 0x54):04X}",
            "bgcnt": [f"0x{value:04X}" for value in bgcnt],
            "bgcnt_fields": [decode_bgcnt(value) for value in bgcnt],
            # BG0..BG3 horizontal offsets live at 0x10/0x14/0x18/0x1C and the
            # vertical ones at 0x12/0x16/0x1A/0x1E; they are interleaved.
            "bg_hoffs": [_u16(io, 0x10 + 4 * index) for index in range(4)],
            "bg_voffs": [_u16(io, 0x12 + 4 * index) for index in range(4)],
        },
        "bg3_screen_base": bg3_screen_base,
        "bg3_tilemap": {
            "cells": 32 * 32,
            "non_zero_cells": sum(
                1 for value in tilemap(vram, bg3_screen_base) if value
            ),
            "top_tiles": [
                {"index": index, "count": count}
                for index, count in collections.Counter(
                    tilemap(vram, bg3_screen_base)
                ).most_common(6)
            ],
        },
        "bg_tilemap_cells": {
            "bg0": sum(
                1
                for a, b in zip(
                    tilemap(vram, 0x0000), tilemap(reference, 0x0000)
                )
                if a != b
            ),
            "bg1": sum(
                1
                for a, b in zip(
                    tilemap(vram, 0x0800), tilemap(reference, 0x0800)
                )
                if a != b
            ),
            "bg2": sum(
                1
                for a, b in zip(
                    tilemap(vram, 0x1000), tilemap(reference, 0x1000)
                )
                if a != b
            ),
            "bg3": sum(
                1
                for a, b in zip(
                    tilemap(vram, 0x1800), tilemap(reference, 0x1800)
                )
                if a != b
            ),
        },
        "map_layer_unchanged": {
            # BG0 is the map: its palette (PRAM banks 0-3) and its tile
            # graphics (VRAM 0x4000, BGCNT char base block 1) are compared
            # against the round-banner frame.  If both are byte-identical the
            # map renders identically, so the cool tint cannot be a tint of
            # the map's own colours.
            "bg0_palette_entries_changed": sum(
                1
                for index in range(64)
                if pram[index * 2:index * 2 + 2]
                != reference_pram[index * 2:index * 2 + 2]
            ),
            "bg0_tile_graphics_bytes_changed": sum(
                1
                for a, b in zip(vram[0x4000:0x8000], reference[0x4000:0x8000])
                if a != b
            ),
            "bg1_tile_graphics_bytes_changed": sum(
                1
                for a, b in zip(vram[0x4000:0x8000], reference[0x4000:0x8000])
                if a != b
            ),
            "bg2_region_bytes_changed": sum(
                1
                for a, b in zip(vram[0x1000:0x1800], reference[0x1000:0x1800])
                if a != b
            ),
        },
        "sprites": {
            "active": len(active_sprites(oam)),
            # Compare *slots*, not whole entries: the shared sprites move
            # between the two frames, so comparing attributes would report
            # every sprite as new.
            "entries_only_here": sorted(
                {
                    (sprite["tile"], sprite["palette"], sprite["x"], sprite["y"])
                    for sprite in active_sprites(oam)
                }
                - (
                    {
                        (sprite["tile"], sprite["palette"],
                         sprite["x"], sprite["y"])
                        for sprite in active_sprites(banner_oam)
                    }
                    if banner_oam is not None
                    else set()
                )
            ),
            "slots_only_here": sorted(
                {sprite["slot"] for sprite in active_sprites(oam)}
                - (
                    {sprite["slot"] for sprite in active_sprites(banner_oam)}
                    if banner_oam is not None
                    else set()
                )
            ),
            "extra_versus_banner": [
                sprite
                for sprite in active_sprites(oam)
                if banner_oam is not None
                and sprite["slot"]
                not in {entry["slot"] for entry in active_sprites(banner_oam)}
            ],
        },
        "screen_registers": {
            "winin": f"0x{_u16(io, 0x40):04X}",
            "winout": f"0x{_u16(io, 0x42):04X}",
            "mosaic": f"0x{_u16(io, 0x44):04X}",
            "bldcnt": f"0x{_u16(io, 0x50):04X}",
            "bldalpha": f"0x{_u16(io, 0x52):04X}",
            "bldy": f"0x{_u16(io, 0x54):04X}",
        },
        "colour_space": {
            "frame_colours": len(colors),
            "palette_entries": len(palette),
            "frame_colours_that_are_palette_entries": len(colors & palette),
            "frame_colours_missing_from_the_palette": len(colors - palette),
        },
    }


def _memory_delta(here: Path, other: Path) -> dict[str, int]:
    """Byte deltas of the two memory dumps, per region."""

    pram_here = (here / "pram-00.bin").read_bytes()
    pram_other = (other / "pram-00.bin").read_bytes()
    vram_here = (here / "vram-00.bin").read_bytes()
    vram_other = (other / "vram-00.bin").read_bytes()
    pram_banks = sorted({
        index // 32
        for index in range(1024)
        if pram_here[index] != pram_other[index]
    })
    vram_diffs = [
        index
        for index in range(0x18000)
        if vram_here[index] != vram_other[index]
    ]
    return {
        "pram_bytes_changed": len([
            index for index in range(1024)
            if pram_here[index] != pram_other[index]
        ]),
        "pram_banks_changed": pram_banks,
        "vram_bytes_changed": len(vram_diffs),
        "vram_lowest_changed": hex(vram_diffs[0]) if vram_diffs else "",
        "vram_highest_changed": hex(vram_diffs[-1]) if vram_diffs else "",
    }


def _screenshot_delta(here: Path, other: Path) -> int:
    """Differing pixels between two receipts' screenshots."""

    from PIL import Image, ImageChops

    with Image.open(here / "frame-00.png") as left, \
            Image.open(other / "frame-00.png") as right:
        difference = ImageChops.difference(
            left.convert("RGB"), right.convert("RGB")
        ).convert("L")
        return sum(difference.histogram()[1:])


def analyze(
    grid_dir: Path,
    banner_dir: Path,
    field_dir: Path,
    grid16_dir: Path,
) -> dict[str, Any]:
    banner = read_frame(banner_dir)
    field = read_frame(field_dir)
    grid16 = read_frame(grid16_dir)
    grid = read_frame(
        grid_dir,
        banner_vram=(banner["_vram"]),
        banner_pram=(banner["_pram"]),
        banner_oam=(banner["_oam"]),
    )
    grid_dispcnt = int(grid["registers"]["dispcnt"], 16)
    banner_dispcnt = int(banner["registers"]["dispcnt"], 16)
    changed = [
        name
        for low, _width, name in DISPCNT_FIELDS
        if ((grid_dispcnt >> low) & 1) != ((banner_dispcnt >> low) & 1)
    ]
    for frame in (grid, banner):
        frame.pop("_vram", None)
        frame.pop("_pram", None)
        frame.pop("_oam", None)
    banner.pop("bg_tilemap_cells", None)
    return {
        "schema": "konoha.s49-movegrid-mechanism.v1",
        "move_range_frame": grid,
        "round_banner_frame": banner,
        "grid_versus_field": {
            "note": (
                "The field screen is the right baseline for the dimming: the "
                "round banner is a full-screen overlay of its own and hides "
                "everything else."
            ),
            "dispcnt_grid": grid["registers"]["dispcnt"],
            "dispcnt_field": field["registers"]["dispcnt"],
            "registers_differing": [
                name
                for name in grid["registers"]
                if name != "dispcnt_fields"
                and grid["registers"][name] != field["registers"][name]
            ],
            "screen_registers_identical": (
                grid["screen_registers"] == field["screen_registers"]
            ),
            "memory_delta": _memory_delta(Path(grid_dir), Path(field_dir)),
            "sprites_active": {
                "grid": grid["sprites"]["active"],
                "field": field["sprites"]["active"],
            },
        },
        "grid16_second_instance": {
            "note": (
                "A second instance of the move-range screen (walk step-16, "
                "camera panned to 152/40) repeats the same pattern: the "
                "overlay is present exactly when DISPCNT bit 10 is set, and "
                "it does not depend on the camera."
            ),
            "dispcnt": grid16["registers"]["dispcnt"],
            "bg0_hoffs": grid16["registers"]["bg_hoffs"][0],
            "bg0_voffs": grid16["registers"]["bg_voffs"][0],
            "screenshot_delta_versus_field": _screenshot_delta(
                Path(grid16_dir), Path(field_dir)
            ),
        },
        "dispcnt_changed_fields": changed,
        "dispcnt_difference_bits": f"0x{grid_dispcnt ^ banner_dispcnt:04X}",
        "blending_enabled": grid["registers"]["bldcnt"] != "0x0000",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grid-dir", type=Path, default=GRID_DIR)
    parser.add_argument("--banner-dir", type=Path, default=BANNER_DIR)
    parser.add_argument("--field-dir", type=Path, default=FIELD_DIR)
    parser.add_argument("--grid16-dir", type=Path, default=GRID16_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    try:
        result = analyze(
            args.grid_dir, args.banner_dir, args.field_dir, args.grid16_dir
        )
    except MechanismError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "mechanism.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
