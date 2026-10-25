#!/usr/bin/env python3
"""Probe the ORIGINAL ROM's background bit depth from a captured GPU frame.

Input: a capture directory produced by `mgba_frame_palette_sequence.lua`
(`pram-NN.bin`, `vram-NN.bin`, `io-NN.bin`, `frame-NN.png`).

Method
------
A GBA background tile is 8x8 pixels.  A **4bpp** background can only show 16
colours per 8x8 tile, and those 16 colours are one *palette bank* (16
consecutive entries of palette RAM).  An **8bpp** background can show up to 256
colours in the same tile, drawn from the whole palette RAM.

So: map every rendered pixel back to its palette-RAM index, then check for each
8x8 block whether all of its palette indices live inside a single 16-entry
bank.  If (almost) every block of a region satisfies that, the region is
4bpp.  If blocks routinely span several banks, the region is 8bpp.

The tool reports, per 8x8 block, how many distinct 16-entry banks it touches,
so the caller can separate "one layer" blocks from mixed blocks.

Usage:
    python probe_bg_bpp.py --capture <dir> [--rows 0 128] [--verbose]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import struct
import sys
from collections import Counter


def read_pram(path: pathlib.Path) -> list[tuple[int, int, int]]:
    """Palette RAM dump -> list of RGB triples (512 entries)."""
    raw = path.read_bytes()
    if len(raw) % 2:
        raw = raw[:-1]
    out = []
    for (raw_color,) in struct.iter_unpack("<H", raw):
        r = raw_color & 0x1F
        g = (raw_color >> 5) & 0x1F
        b = (raw_color >> 10) & 0x1F
        # GBA 5-bit channel -> 8-bit: (c << 3) | (c >> 2)
        out.append(((r << 3) | (r >> 2), (g << 3) | (g >> 2), (b << 3) | (b >> 2)))
    return out


def read_io(path: pathlib.Path) -> dict[str, int]:
    raw = path.read_bytes()
    names = {
        0x00: "DISPCNT",
        0x02: "BG0CNT",
        0x04: "BG1CNT",
        0x06: "BG2CNT",
        0x08: "BG3CNT",
    }
    out = {}
    for off, name in names.items():
        out[name] = int.from_bytes(raw[off : off + 2], "little")
    return out


def decode_dispcnt(value: int) -> dict[str, object]:
    """GBA DISPCNT bit layout (Mode 0/1/2).

    bit 0-2   BG0-BG2 enable
    bit 3     BG3 enable
    bit 4-7   BG0-BG3 character base block (0=0x00000, 1=0x04000)
    bit 8-11  BG0-BG3 screen base block  (0=0x00000, 1=0x00800)
    bit 12-14 video mode
    bit 15    1st/2nd frame selection
    """
    return {
        "raw": f"0x{value:04X}",
        "mode": (value >> 12) & 7,
        "bg_enable": {
            "BG0": value & 1,
            "BG1": (value >> 1) & 1,
            "BG2": (value >> 2) & 1,
            "BG3": (value >> 3) & 1,
        },
        "bg_char_base": {
            "BG0": f"0x{((value >> 4) & 1) * 0x4000:05X}",
            "BG1": f"0x{((value >> 5) & 1) * 0x4000:05X}",
            "BG2": f"0x{((value >> 6) & 1) * 0x4000:05X}",
            "BG3": f"0x{((value >> 7) & 1) * 0x4000:05X}",
        },
        "bg_screen_base": {
            "BG0": f"0x{((value >> 8) & 1) * 0x800:04X}",
            "BG1": f"0x{((value >> 9) & 1) * 0x800:04X}",
            "BG2": f"0x{((value >> 10) & 1) * 0x800:04X}",
            "BG3": f"0x{((value >> 11) & 1) * 0x800:04X}",
        },
    }


def decode_bgx_cnt(value: int) -> dict[str, object]:
    """GBA BGxCNT bit layout (Mode 0/1/2).

    bit 0-1   priority
    bit 2     character base block (0=0x00000, 1=0x04000)
    bit 3     mosaic disable
    bit 4-5   2D/3D (Mode 1,2)
    bit 6     display area overflow
    bit 7-8   screen size
    bit 9-12  screen base block
    bit 13    character base block (Mode 0)
    bit 14    colour depth (0=16/16 = 4bpp, 1=256/256 = 8bpp)
    bit 15    unused
    """
    return {
        "raw": f"0x{value:04X}",
        "priority": value & 3,
        "char_base": f"0x{((value >> 2) & 1) * 0x4000:05X}",
        "screen_base": f"0x{((value >> 9) & 0xF) * 0x800:04X}",
        "screen_size": (value >> 7) & 3,
        "color_depth_bit14": (value >> 14) & 1,
    }


def analyse(
    capture: pathlib.Path,
    row_range: tuple[int, int] | None,
    verbose: bool,
) -> dict[str, object]:
    pram = read_pram(capture / "pram-00.bin")
    io_regs = read_io(capture / "io-00.bin")

    try:
        from PIL import Image
    except ImportError:  # pragma: no cover
        raise SystemExit("Pillow is required")

    image = Image.open(capture / "frame-00.png").convert("RGB")
    width, height = image.size
    pixels = list(image.getdata())

    color_to_index: dict[tuple[int, int, int], list[int]] = {}
    for index, color in enumerate(pram):
        color_to_index.setdefault(color, []).append(index)

    top = row_range[0] if row_range else 0
    bottom = min(row_range[1] if row_range else height, height)

    blocks: list[dict[str, object]] = []
    for by in range(top, bottom - 7, 8):
        for bx in range(0, width - 7, 8):
            banks: Counter[int] = Counter()
            missing = 0
            for y in range(by, by + 8):
                row = y * width
                for x in range(bx, bx + 8):
                    color = pixels[row + x]
                    indices = color_to_index.get(color)
                    if not indices:
                        missing += 1
                        continue
                    banks[min(indices) // 16] += 1
            blocks.append(
                {
                    "bx": bx,
                    "by": by,
                    "banks": sorted(banks),
                    "bank_count": len(banks),
                    "missing": missing,
                }
            )

    single = [b for b in blocks if b["bank_count"] == 1]
    multi = [b for b in blocks if b["bank_count"] > 1]
    bank_histogram = Counter(b["bank_count"] for b in blocks)

    result: dict[str, object] = {
        "capture": str(capture),
        "frame_size": [width, height],
        "row_range": [top, bottom],
        "io": {name: decode_dispcnt(io_regs[name]) if name == "DISPCNT" else decode_bgx_cnt(io_regs[name]) for name in io_regs},
        "palette_entries": len(pram),
        "distinct_pram_colors": len({c for c in pram}),
        "blocks_total": len(blocks),
        "blocks_single_bank": len(single),
        "blocks_multi_bank": len(multi),
        "blocks_unmapped_pixels": sum(b["missing"] for b in blocks),
        "single_bank_ratio": round(len(single) / len(blocks), 4) if blocks else None,
        "bank_count_histogram": dict(sorted(bank_histogram.items())),
        "bank_histogram_top": [
            [bank, count] for bank, count in Counter(
                bank for b in blocks for bank in b["banks"]
            ).most_common(16)
        ],
    }
    if verbose:
        result["multi_bank_examples"] = [b for b in multi[:40]]
    return result


def ascii_map(
    capture: pathlib.Path,
    row_range: tuple[int, int] | None,
) -> str:
    """Per-8x8-block palette-bank count map ('.' = single bank, digits = more)."""
    pram = read_pram(capture / "pram-00.bin")
    from PIL import Image

    image = Image.open(capture / "frame-00.png").convert("RGB")
    width, height = image.size
    pixels = list(image.getdata())
    color_to_index: dict[tuple[int, int, int], list[int]] = {}
    for index, color in enumerate(pram):
        color_to_index.setdefault(color, []).append(index)

    top = row_range[0] if row_range else 0
    bottom = min(row_range[1] if row_range else height, height)
    lines = []
    for by in range(top, bottom - 7, 8):
        row_chars = []
        for bx in range(0, width - 7, 8):
            banks: Counter[int] = Counter()
            for y in range(by, by + 8):
                row = y * width
                for x in range(bx, bx + 8):
                    indices = color_to_index.get(pixels[row + x])
                    if indices:
                        banks[min(indices) // 16] += 1
            count = len(banks)
            row_chars.append("." if count == 1 else str(min(count, 9)))
        lines.append(f"y{by:03d} " + "".join(row_chars))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", required=True)
    parser.add_argument("--rows", nargs=2, type=int, default=None)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--ascii", action="store_true")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    capture = pathlib.Path(args.capture)
    row_range = (args.rows[0], args.rows[1]) if args.rows else None
    result = analyse(capture, row_range, args.verbose)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.ascii:
        print("--- 8x8 block palette-bank count map ---")
        print(ascii_map(capture, row_range))
    if args.out:
        out = pathlib.Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
