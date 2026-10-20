#!/usr/bin/env python3
"""Portrait (头像) and sprite asset format.

A portrait is assembled from pieces:

    portrait table  0x5A4DEC + id*40 + expression*8  -> (gfx ptr, palette ptr)
    piece table     0x4643C0 + j*20 -> (tile u32, x u16, y u16, w u16, h u16)

Each piece points into a 4bpp tile sheet: a piece covers `w x h` pixels, and
its tiles are laid out `w/8` wide by `h/8` tall, 32 bytes per tile.

The third-party editor hard-codes a 80x80 portrait and a 20-piece limit.
This tool re-derives both from the ROM's own data instead of assuming them.

Usage:
    python tools/portrait_assets.py
    python tools/portrait_assets.py --json build/portrait_assets.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import struct
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from tools import text_codec  # noqa: E402

PORTRAIT_TABLE = 0x5A4DEC
PORTRAIT_STRIDE = 40
EXPR_STRIDE = 8
PIECE_TABLE = 0x4643C0
PIECE_STRIDE = 20
PIECE_LIMIT = 32          # scan window; the data ends with a 0xFFFF marker
TILE_BYTES = 32
TILE_PIXELS = 8           # 4bpp tile is 8x8


def lz_decompressed_size(rom: bytes, ptr: int) -> int | None:
    """Size of the LZ77 stream at `ptr` (ROM address), if it looks like one."""
    off = ptr - 0x08000000
    if not (0 <= off < len(rom) - 8):
        return None
    header = int.from_bytes(rom[off:off + 4], "little")
    size = (header >> 8) & 0xFFFFFF
    return size


def read_pieces(rom: bytes) -> list[dict]:
    pieces = []
    for j in range(PIECE_LIMIT):
        p = PIECE_TABLE + j * PIECE_STRIDE
        tile, x, y, w, h = struct.unpack_from("<IHHHH", rom, p)
        if tile == 0xFFFF:
            pieces.append({"index": j, "end_marker": True})
            break
        pieces.append({
            "index": j,
            "end_marker": False,
            "tile": tile,
            "x": x, "y": y, "w": w, "h": h,
            "tiles_wide": (w + TILE_PIXELS - 1) // TILE_PIXELS,
            "tiles_high": (h + TILE_PIXELS - 1) // TILE_PIXELS,
        })
    return pieces


def read_portraits(rom: bytes) -> list[dict]:
    out = []
    for pid in range(0, 64):
        row = {"id": pid, "expressions": []}
        for expr in range(PORTRAIT_STRIDE // EXPR_STRIDE):
            p = PORTRAIT_TABLE + pid * PORTRAIT_STRIDE + expr * EXPR_STRIDE
            gfx, pal = struct.unpack_from("<II", rom, p)
            if gfx == 0 and pal == 0:
                continue
            row["expressions"].append({
                "expression": expr,
                "gfx": gfx,
                "palette": pal,
                # gfx is LZ77-compressed and decompresses to 80*80/2 = 6400
                # bytes of 4bpp indices.
                "gfx_lz_size": lz_decompressed_size(rom, gfx),
                # The palette is *raw*, not compressed: 64 colours x 2 bytes
                # (BGR555) = 128 bytes.
                "palette_is_raw_128": (
                    0x08000000 <= pal < 0x09000000
                    and pal - 0x08000000 + 128 <= len(rom)
                ),
            })
        if row["expressions"]:
            out.append(row)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rom", default=None)
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    rom_path = text_codec.resolve_rom(args.rom)
    rom = rom_path.read_bytes()
    pieces = read_pieces(rom)
    portraits = read_portraits(rom)

    live_pieces = [p for p in pieces if not p.get("end_marker")]
    width = max((p["x"] + p["w"] for p in live_pieces), default=0)
    height = max((p["y"] + p["h"] for p in live_pieces), default=0)
    gfx_sizes = sorted({e["gfx_lz_size"] for r in portraits for e in r["expressions"]
                        if e["gfx_lz_size"]})
    raw_palettes = sum(
        1 for r in portraits for e in r["expressions"] if e["palette_is_raw_128"])

    report = {
        "rom": str(rom_path),
        "portrait_table": hex(PORTRAIT_TABLE),
        "portrait_stride": PORTRAIT_STRIDE,
        "piece_table": hex(PIECE_TABLE),
        "piece_stride": PIECE_STRIDE,
        "piece_count": len(live_pieces),
        "assembled_size": [width, height],
        "gfx_lz_sizes": gfx_sizes,
        "raw_128_byte_palettes": raw_palettes,
        "pieces": pieces,
        "portraits": portraits,
    }
    if args.json:
        pathlib.Path(args.json).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"portrait table @ {hex(PORTRAIT_TABLE)} (id*{PORTRAIT_STRIDE} + "
          f"expr*{EXPR_STRIDE} -> gfx, palette)")
    print(f"piece table    @ {hex(PIECE_TABLE)} (stride {PIECE_STRIDE})")
    print()
    print(f"pieces: {len(live_pieces)}  assembled size: {width} x {height}")
    for p in live_pieces:
        print(f"  [{p['index']:2d}] tile={p['tile']:<4} "
              f"({p['x']},{p['y']}) {p['w']}x{p['h']} "
              f"= {p['tiles_wide']}x{p['tiles_high']} tiles")
    print()
    print(f"portrait ids with data: {len(portraits)} "
          f"-> {[r['id'] for r in portraits]}")
    print(f"gfx LZ sizes     : {gfx_sizes}")
    print(f"raw 128-byte palettes: {raw_palettes} of "
          f"{sum(len(r['expressions']) for r in portraits)} expressions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
