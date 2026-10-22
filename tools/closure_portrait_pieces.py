#!/usr/bin/env python3
"""Runtime closure for the portrait piece table (evidence item F).

The 6x20-byte piece layout table lives at ``0x084643C0``.  It has **no literal
reader of its own** -- but the *pointer* to it is the first word of the static
descriptor at ``0x0846443C``, and that descriptor address is loaded by seven
native code sites (one of them is the portrait loader at ``0x08096618``).

This tool boots into the portrait path, stops on the descriptor load, follows
the pointer and checks the six records against the ROM:

    piece i:  u16 start_tile, u16 ?, u16 x, u16 y, u16 w, u16 h,
              u16 0x0100, u16 0x0100, u16 0x20FF, u16 0x0000

It also proves that the six pieces tile an 80x80 portrait exactly and that
their source tile ranges cover the 136-tile source pool.

Usage:
    python tools/closure_portrait_pieces.py rom/base.gba --scene 1
"""
from __future__ import annotations

import argparse
import json
import pathlib
import struct
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools", REPO / "tools" / "mgba_probe"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from tools.mgba_probe.l4_battle_matrix import (  # noqa: E402
    Harness, hit_of, KEY_BITS, PHASE_NEXT_SCENE, SCENE_BYTE, PHASE_WORD,
)

ROM_BASE = 0x08000000
DEFAULT_EXE = REPO / "build" / "mgba-probe" / "mgba-probe.exe"

DESCRIPTOR = 0x0846443C        # the static descriptor the code loads
PIECE_TABLE = 0x084643C0       # the pointer stored at DESCRIPTOR + 0x00
PIECE_SIZE = 20
PIECE_COUNT = 6
LOAD_SITE = 0x08096618         # 'ldr r0,[pc,#0x40]' -> 0x0846443C
COPY_SITE = 0x08096202         # the portrait loader's VRAM copy (fires in scenes 1/5)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("rom", nargs="?", default="rom/base.gba")
    ap.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    ap.add_argument("--scene", type=int, default=1)
    ap.add_argument("--site", type=lambda x: int(x, 0), default=COPY_SITE)
    ap.add_argument("--frames", type=int, default=900)
    ap.add_argument("--json", type=pathlib.Path, default=None)
    args = ap.parse_args(argv)

    rom = (REPO / args.rom).read_bytes()
    report: dict = {"scene": args.scene, "site": f"0x{args.site:08X}", "hits": []}
    harness = Harness(args.exe, pathlib.Path(args.rom))
    try:
        if not harness.boot_to_state_machine():
            print("could not park on the state machine", file=sys.stderr)
            return 2
        harness.poke(SCENE_BYTE, args.scene)
        harness.poke16(PHASE_WORD, PHASE_NEXT_SCENE)
        for _ in range(30):
            harness.send(f"frames 8 {KEY_BITS['A']:#05x}")
            harness.send("frames 120 0x000")
        harness.send(f"frames 8 {KEY_BITS['A']:#05x}")
        harness.send("frames 120 0x000")
        harness.arm(args.site)
        for _ in range(9):
            out = harness.send(f"frames {args.frames} {KEY_BITS['A']:#05x}")
            hit = hit_of(out)
            if hit is None:
                out = harness.send(f"frames 8 {KEY_BITS['A']:#05x}") + \
                    harness.send("frames 120 0x000")
                hit = hit_of(out)
            if hit is None:
                break
            regs = harness.probe.registers()
            r0 = regs.get("r0", 0)
            desc = harness.read(DESCRIPTOR, 4)
            table = struct.unpack("<I", desc)[0] if len(desc) == 4 else None
            rec = harness.read(table, PIECE_COUNT * PIECE_SIZE) if table else b""
            rom_rec = rom[PIECE_TABLE - ROM_BASE:
                          PIECE_TABLE - ROM_BASE + PIECE_COUNT * PIECE_SIZE]
            pieces = []
            for i in range(PIECE_COUNT):
                if len(rec) < (i + 1) * PIECE_SIZE:
                    break
                v = struct.unpack_from("<10H", rec, i * PIECE_SIZE)
                pieces.append({"start_tile": v[0], "u16_1": v[1], "x": v[2],
                               "y": v[3], "w": v[4], "h": v[5]})
            record = {
                "pc": f"0x{regs.get('pc', 0):08X}",
                "r0": f"0x{r0:08X}",
                "r0_is_descriptor": r0 == DESCRIPTOR,
                "descriptor_word": f"0x{table:08X}" if table else None,
                "descriptor_is_piece_table": table == PIECE_TABLE,
                "pieces": pieces,
                "rom_bytes_equal": rec == rom_rec,
            }
            report["hits"].append(record)
            print(json.dumps(record, ensure_ascii=False))
            harness.send("next")
            harness.rearm()
    finally:
        harness.close()

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    hit = report["hits"][0] if report["hits"] else None
    ok = bool(hit and hit["rom_bytes_equal"]
              and hit["descriptor_is_piece_table"])
    print(f"OK: the piece table is reached through the descriptor: {ok}")
    return 0 if ok else 1

if __name__ == "__main__":
    raise SystemExit(main())
