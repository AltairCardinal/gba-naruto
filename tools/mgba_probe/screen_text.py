#!/usr/bin/env python3
"""Read the text off the emulated screen and map it back to font codes.

Why
---
`notes/font-encoding.md` says the game renders Chinese from its own
baked-in double-byte font.  That claim was only ever proven *statically*
(segment table + round trip).  This tool closes the loop against the real
picture:

  1. boot the game in the headless probe, press the keys that reach a
     dialogue box, and grab mGBA's own rendered frame plus PALRAM;
  2. turn every screen pixel back into a palette index, so the picture can
     be compared with the ROM's tile data;
  3. compare each 8x16 cell of the text area with every glyph of the font
     segment table (`0x53D644`), reading the 32 bytes per glyph as
     **8 wide x 16 tall, 2bpp** (two stacked 8x8 tiles);
  4. decode the matched codes with `tools/text_codec.py`.

The result is a checkable statement: *these exact font codes produced
these exact pixels*.

Caveat found while building this (2026-10-20): the **dialogue ideographs**
do not come from the `0x53D644` table - their bitmaps live in a separate
ROM table around `0x0813E040` / `0x0813E120` (see
`notes/font-encoding.md` 1.2).  Only the small punctuation matches the
`0x53D644` bitmaps bit-for-bit, so the tool reports "CONFIRMED bit-exact"
cells separately from best-effort guesses.

The picture this tool works on is `notes/evidence/story-scene-l3.png`
(produced by `tools/mgba_probe/render_screen.py`); it is the visual
evidence for the text-encoding structure.

Usage:
    python tools/mgba_probe/screen_text.py rom/base.gba \
        --press START --press A --press A --press A --press A
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import threading

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

WIDTH, HEIGHT = 240, 160
GLYPH_W, GLYPH_H = 8, 16
GLYPH_BYTES = 32


# --------------------------------------------------------------------------
# capture
# --------------------------------------------------------------------------
def capture(rom: pathlib.Path, exe: pathlib.Path, boot_frames: int,
            presses: list[str], settle_frames: int):
    """Run the game, return (rgba_frame, palram, rom_bytes)."""
    proc = subprocess.Popen(
        [str(exe), str(rom)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
        bufsize=1)
    threading.Thread(target=lambda: [None for _ in proc.stderr], daemon=True).start()

    def send(command: str) -> list[str]:
        token = "__end__"
        proc.stdin.write(f"{command}\necho {token}\n")
        proc.stdin.flush()
        lines = []
        while True:
            line = proc.stdout.readline()
            if not line:
                raise EOFError("probe exited")
            line = line.rstrip("\r\n")
            if line == token:
                return lines
            lines.append(line)

    def read(address: int, length: int) -> bytes:
        out = send(f"dump 0x{address:08X} {length}")
        payload = []
        for line in out:
            line = line.strip()
            if line and all(c in "0123456789abcdefABCDEF" for c in line):
                payload.append(line)
        try:
            return bytes.fromhex("".join(payload))
        except ValueError:
            return b""

    handle = HERE / "_screen_text_frame.rgba"
    try:
        send(f"frames {boot_frames} 0x000")
        for press in presses:
            bit = {"A": 0x001, "B": 0x002, "START": 0x008,
                   "SELECT": 0x004, "UP": 0x040, "DOWN": 0x080,
                   "LEFT": 0x020, "RIGHT": 0x010}.get(press.upper(), 0)
            send(f"frames 8 {bit:#05x}")
            send(f"frames {settle_frames} 0x000")
        send(f"rawshot {handle}")
        frame = handle.read_bytes()
        palram = read(0x05000000, 0x200)
    finally:
        try:
            send("quit")
        except Exception:
            pass
        try:
            proc.stdin.close()
        except Exception:
            pass
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
        handle.unlink(missing_ok=True)
    return frame, palram


def to_rgb8(v5: int) -> tuple[int, int, int]:
    """mGBA's own 5-bit -> 8-bit expansion (mgba/core/interface.h)."""
    r5, g5, b5 = v5 & 0x1F, (v5 >> 5) & 0x1F, (v5 >> 10) & 0x1F
    r = (r5 << 3) | ((r5 << 3) >> 5)
    g = (g5 << 3) | ((g5 << 3) >> 5)
    b = (b5 << 3) | ((b5 << 3) >> 5)
    return (r, g, b)


def palette_map(palram: bytes) -> dict[tuple[int, int, int], int]:
    lookup: dict[tuple[int, int, int], int] = {}
    for i in range(0, len(palram) - 1, 2):
        colour = to_rgb8(palram[i] | (palram[i + 1] << 8))
        lookup.setdefault(colour, i // 2)
    return lookup


# --------------------------------------------------------------------------
# font glyphs: 32 bytes = 8 wide x 16 tall, 2bpp
# --------------------------------------------------------------------------
def glyph_masks(rom: bytes) -> dict[int, int]:
    """font code -> 128-bit ink mask (bit 0 = top-left pixel)."""
    import konoha_font

    masks: dict[int, int] = {}
    for segment in konoha_font.read_segments(rom):
        for i in range(segment.count):
            code = segment.start + i
            data = rom[segment.offset + i * GLYPH_BYTES:
                       segment.offset + (i + 1) * GLYPH_BYTES]
            mask = 0
            for row in range(GLYPH_H):
                for half in range(2):
                    byte = data[row * 2 + half]
                    for px in (0, 1):
                        index = (byte >> (2 * (1 - px))) & 3
                        if index:
                            mask |= 1 << (row * GLYPH_W + half * 2 + px)
            masks[code] = mask
    return masks


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rom", type=pathlib.Path)
    ap.add_argument("--exe", type=pathlib.Path,
                    default=REPO / "build" / "mgba-probe" / "mgba-probe.exe")
    ap.add_argument("--boot-frames", type=int, default=1500)
    ap.add_argument("--press", action="append", default=[])
    ap.add_argument("--settle-frames", type=int, default=120)
    ap.add_argument("--rect", default=None,
                    help="text area as x,y,w,h (default: whole screen)")
    ap.add_argument("--min-hit", type=int, default=3,
                    help="minimum glyph pixels that must coincide with the cell")
    ap.add_argument("--json", type=pathlib.Path, default=None)
    args = ap.parse_args()

    if not args.exe.exists():
        print(f"ERR {args.exe} missing; run: python tools/mgba_probe/build.py",
              file=sys.stderr)
        return 2

    frame, palram = capture(args.rom, args.exe, args.boot_frames, args.press,
                            args.settle_frames)
    rom = args.rom.read_bytes()
    lookup = palette_map(palram)

    screen = []
    for y in range(HEIGHT):
        row = []
        base = y * WIDTH * 4
        for x in range(WIDTH):
            o = base + x * 4
            row.append((frame[o], frame[o + 1], frame[o + 2]))
        screen.append(row)

    # Background: the most common colour in the text area.
    from collections import Counter
    counts: Counter = Counter()
    for y in range(100, 140):
        for x in range(16, 232):
            counts[screen[y][x]] += 1
    background = counts.most_common(1)[0][0]

    glyphs = glyph_masks(rom)
    print(f"font glyphs: {len(glyphs)}  background: {background}")

    if args.rect:
        x0, y0, w, h = (int(v, 0) for v in args.rect.split(","))
    else:
        x0, y0, w, h = 16, 96, 216, 44

    rows = []
    matched = 0
    for y in range(y0, y0 + h - GLYPH_H + 1, 8):
        line = []
        for x in range(x0, x0 + w - GLYPH_W + 1, 8):
            mask = 0
            ink = 0
            for yy in range(GLYPH_H):
                for xx in range(GLYPH_W):
                    if screen[y + yy][x + xx] != background:
                        mask |= 1 << (yy * GLYPH_W + xx)
                        ink += 1
            if ink == 0:
                line.append({"code": None, "char": " ", "ink": 0, "diff": None})
                continue
            # The dialogue is drawn with a shadow / semi-transparent edges, so
            # the screen ink is neither a subset nor a superset of the glyph
            # ink.  The discriminating signal is *coincidence*: the true
            # glyph explains far more screen pixels than any other glyph.
            #
            # A cell only counts as CONFIRMED when the glyph's ink is
            # *identical* to the cell's ink; anything else is reported as a
            # best-effort guess and must not be treated as evidence.
            best_code, best_hit, best_missing = None, -1, None
            for code, glyph in glyphs.items():
                hit = bin(glyph & mask).count("1")
                if hit <= best_hit:
                    continue
                best_code = code
                best_hit = hit
                best_missing = bin(glyph & ~mask).count("1")
            exact = best_code is not None and best_missing == 0 and \
                bin(mask & ~glyphs[best_code]).count("1") == 0
            if best_code is None or best_hit < args.min_hit:
                line.append({"code": None, "char": " ", "ink": ink,
                             "hit": best_hit, "missing": best_missing,
                             "exact": False})
                continue
            matched += 1
            import text_codec
            try:
                char = text_codec.decode(bytes([best_code >> 8, best_code & 0xFF]))
            except Exception:
                char = "?"
            line.append({"code": best_code, "char": char, "ink": ink,
                         "hit": best_hit, "missing": best_missing,
                         "exact": exact,
                         "diff": best_hit + (best_missing or 0)})
        rows.append({"y": y, "cells": line})

    report = {
        "rom": str(args.rom),
        "presses": args.press,
        "rect": [x0, y0, w, h],
        "glyph_format": "8x16 2bpp (32 bytes per glyph)",
        "cells_matched": matched,
        "rows": rows,
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8", newline="\n")

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for row in rows:
        text = "".join(cell["char"] for cell in row["cells"])
        print(f"y={row['y']:3d} |{text}|")
    print()
    exact_cells = [
        (row["y"], cell)
        for row in rows for cell in row["cells"] if cell.get("exact")
    ]
    print(f"cells matched (best effort): {matched}")
    print(f"cells CONFIRMED bit-exact    : {len(exact_cells)}")
    for y, cell in exact_cells:
        print(f"   y={y:3d} code 0x{cell['code']:04X} {cell['char']!r} "
              f"({cell['ink']} ink px)")
    if not exact_cells:
        print("   (no bit-exact cell: the dialogue glyphs are NOT the bitmap "
              "in the 0x53D644 table -- see notes/font-encoding.md 1.1)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
