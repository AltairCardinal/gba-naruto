#!/usr/bin/env python3
"""Watch native loaders during the game's own boot / new-game flow.

The scene sweep (tools/closure_scene_sweep.py) dispatches the story
scenes directly and never reaches the level-block loader at 0x08072EDC.
This tool arms the breakpoints **before** the title screen is touched, so
the whole boot flow (title -> new game -> intro) is watched.

Usage:
    python tools/closure_boot_probe.py --breaks 0x08072EDC --json build/boot.json
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

from tools.mgba_probe.l4_battle_matrix import Harness, hit_of, KEY_BITS  # noqa: E402
from tools.mgba_probe.l4_playthrough import Probe, arm  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("rom", nargs="?", default="rom/base.gba")
    ap.add_argument("--exe", type=pathlib.Path,
                    default=REPO / "build" / "mgba-probe" / "mgba-probe.exe")
    ap.add_argument("--breaks", default="0x08072EDC")
    ap.add_argument("--plan", default="START:8,A:8,A:8,A:8,A:20,A:8,A:8")
    ap.add_argument("--settle", type=int, default=240)
    ap.add_argument("--json", type=pathlib.Path, default=None)
    args = ap.parse_args(argv)

    harness = Harness(args.exe, pathlib.Path(args.rom))
    breaks = [int(item, 0) for item in args.breaks.split(",") if item.strip()]
    hits: list[dict] = []
    try:
        harness.send("frames 1500 0x000")
        for address in breaks:
            harness.arm(address)
        for item in args.plan.split(","):
            key, _, frames = item.partition(":")
            mask = KEY_BITS.get(key.strip(), 0)
            out = harness.send(f"frames {int(frames or 8)} {mask:#05x}")
            while True:
                hit = hit_of(out)
                if hit is None:
                    break
                regs = harness.probe.registers()
                entry = {
                    "address": f"0x{hit:08X}",
                    "registers": {k: f"0x{v:08X}" for k, v in sorted(regs.items())},
                }
                sp = regs.get("sp", 0)
                if sp:
                    stack = harness.read(sp, 0x10)
                    entry["stack"] = [f"0x{int.from_bytes(stack[i:i + 4], 'little'):08X}"
                                      for i in range(0, len(stack), 4)]
                hits.append(entry)
                print(f"hit 0x{hit:08X} r0={entry['registers'].get('r0')} "
                      f"r1={entry['registers'].get('r1')} "
                      f"stack={entry.get('stack')}")
                harness.send("next")
                harness.rearm()
                out = harness.send(f"frames {int(frames or 8)} {mask:#05x}")
            harness.send(f"frames {args.settle} 0x000")
    finally:
        harness.close()
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps({"hits": hits}, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8", newline="\n")
    print(f"{len(hits)} hit(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
