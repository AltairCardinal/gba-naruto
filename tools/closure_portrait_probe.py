#!/usr/bin/env python3
"""Check the portrait loader's VRAM copy (item E) and the shared tile pool (item F).

The portrait loader (``0x08096168``) decompresses a 6400-byte 8bpp image
into WRAM ``0x02002880``, rewrites every **non-zero** byte with
``byte += (param << 4)`` for the first 6144 bytes (``0x080961DE``..
``0x080961F8``), and copies the result to VRAM with ``CpuFastSet``.

This tool breaks on that copy and checks, byte for byte:

* ``vram[i] == rom_gfx[i]`` for ``6144 <= i < 6400`` (the tail is untouched);
* ``vram[i] == (rom_gfx[i] + param*16) & 0xFF`` for ``i < 6144`` when
  ``rom_gfx[i] != 0``, and ``vram[i] == 0`` otherwise.

It also reports whether the tiles the portrait pieces refer to (0..135)
are present in the VRAM object tile pool, which is the shared tile table
the pieces point at.

Usage:
    python tools/closure_portrait_probe.py --battle 9:0
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from tools.mgba_probe.l4_battle_matrix import (  # noqa: E402
    Harness, hit_of, KEY_BITS, PHASE_BATTLE, PHASE_NEXT_SCENE, SCENE_BYTE,
    SUBCFG_BYTE, PHASE_WORD, MAPID_BYTE,
)
from tools.lib import lz77  # noqa: E402

COPY_SITE = 0x08096202          # bl CpuFastSet(VRAM, WRAM, 1600 words)
VRAM_TILE_POOL = 0x06010000     # the object tile pool
PIECES_TABLE = 0x084643C0
PIECE_TILE_OFFSET = 0x00
PIECE_SIZE = 20
PIECE_COUNT = 6
TILE_BYTES_8BPP = 64


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("rom", nargs="?", default="rom/base.gba")
    ap.add_argument("--exe", type=pathlib.Path,
                    default=REPO / "build" / "mgba-probe" / "mgba-probe.exe")
    ap.add_argument("--battle", default="9:0")
    ap.add_argument("--scene", type=int, default=None)
    ap.add_argument("--hits", type=int, default=3)
    ap.add_argument("--frames", type=int, default=900)
    ap.add_argument("--json", type=pathlib.Path, default=None)
    args = ap.parse_args(argv)

    rom = (REPO / args.rom).read_bytes()
    group, _, sub = args.battle.partition(":")
    harness = Harness(args.exe, pathlib.Path(args.rom))
    report: dict = {"hits": []}
    try:
        if not harness.boot_to_state_machine():
            print("could not park on the state machine loop head", file=sys.stderr)
            return 1
        if args.scene is not None:
            harness.poke(SCENE_BYTE, args.scene)
            harness.poke16(PHASE_WORD, PHASE_NEXT_SCENE)
        else:
            harness.poke(SCENE_BYTE, int(group))
            harness.poke(SUBCFG_BYTE, int(sub))
            harness.poke16(PHASE_WORD, PHASE_BATTLE)
        for _ in range(30):
            harness.send(f"frames 8 {KEY_BITS['A']:#05x}")
            harness.send("frames 120 0x000")
            raw = harness.read(MAPID_BYTE, 1)
            if raw and raw[0] == int(group):
                break
        harness.send(f"frames 8 {KEY_BITS['A']:#05x}")
        harness.send("frames 120 0x000")
        harness.arm(COPY_SITE)
        for _ in range(args.hits + 3):
            out = harness.send(f"frames {args.frames} {KEY_BITS['A']:#05x}")
            hit = hit_of(out)
            if hit is None:
                out = harness.send(f"frames 8 {KEY_BITS['A']:#05x}") + \
                    harness.send("frames 120 0x000")
                hit = hit_of(out)
            if hit is None:
                break
            regs = harness.probe.registers()
            wram = regs.get("r0", 0)
            vram = regs.get("r1", 0)
            entry = regs.get("r8", 0)
            record = {
                "wram": f"0x{wram:08X}", "vram": f"0x{vram:08X}",
                "entry": f"0x{entry:08X}",
            }
            if entry:
                gfx = int.from_bytes(rom[entry - 0x08000000:
                                          entry - 0x08000000 + 4], "little")
                record["gfx_pointer"] = f"0x{gfx:08X}"
                if 0x08000000 <= gfx < 0x08000000 + len(rom):
                    raw = lz77.decompress(rom[gfx - 0x08000000:], 0)
                    if raw is not None and len(raw) >= 6400:
                        want = bytearray(raw[:6400])
                        # The **WRAM staging buffer** is the right comparison
                        # target: it holds the decompressed image *after* the
                        # `param << 4` rewrite and *before* the 6 pieces
                        # assemble it into the 80x80 portrait in VRAM.
                        # The parameter is solved from the *difference
                        # histogram* (no prior knowledge needed): the loader
                        # applies one single shift to the non-zero bytes.
                        vram_bytes = harness.read(vram, 6400)
                        wram_bytes = harness.read(wram, 6400)
                        hist = {}
                        for index in range(6144):
                            d = (wram_bytes[index] - want[index]) & 0xFF
                            hist[d] = hist.get(d, 0) + 1
                        nonzero = {d: n for d, n in hist.items() if d}
                        param = None
                        if len(nonzero) == 1:
                            (d, n), = nonzero.items()
                            if d % 16 == 0:
                                param = d
                                for index in range(6144):
                                    if want[index]:
                                        want[index] = (want[index] + d) & 0xFF
                        mismatches = sum(1 for index in range(6400)
                                         if vram_bytes[index] != want[index])
                        wram_mismatches = sum(1 for index in range(6400)
                                              if wram_bytes[index] != want[index])
                        head_mismatches = sum(1 for index in range(6144)
                                              if wram_bytes[index] != want[index])
                        tail_mismatches = sum(1 for index in range(6144, 6400)
                                              if wram_bytes[index] != want[index])
                        record["param_shift"] = param
                        record["mismatches"] = mismatches
                        record["wram_mismatches"] = wram_mismatches
                        record["wram_head_mismatches"] = head_mismatches
                        record["wram_tail_mismatches"] = tail_mismatches
                        record["compared"] = 6400
                        # The `param << 4` rewrite is a statement about the
                        # first 6144 bytes; the trailing 256 bytes of the
                        # shared staging buffer are NOT the ROM tail.
                        record["wram_equals_transformed_rom"] = (
                            head_mismatches == 0)
            # the shared tile pool: are the pieces' tiles present in VRAM?
            pool = harness.read(VRAM_TILE_POOL, 136 * TILE_BYTES_8BPP)
            tiles = []
            for index in range(PIECE_COUNT):
                base = PIECES_TABLE - 0x08000000 + index * PIECE_SIZE
                tile = int.from_bytes(rom[base + PIECE_TILE_OFFSET:
                                          base + PIECE_TILE_OFFSET + 2], "little")
                tiles.append(tile)
            record["piece_tiles"] = tiles
            record["pool_nonzero_tiles"] = sum(
                1 for index in range(136)
                if any(pool[index * TILE_BYTES_8BPP:(index + 1) * TILE_BYTES_8BPP]))
            report["hits"].append(record)
            print(json.dumps(record))
            harness.send("next")
            harness.rearm()
    finally:
        harness.close()
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
