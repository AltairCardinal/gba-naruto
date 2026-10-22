#!/usr/bin/env python3
"""Runtime probe for the 2026-10-21 closure work (items A..G).

One process, one game boot, and a list of breakpoints.  At every hit the
tool records the registers and a set of memory windows, so a claim about
"the engine did X" can be checked against a reading instead of against a
recollection.

The battle route is the one proved in
``notes/evidence/l4-battle-matrix-20261021.md`` (see
``tools/mgba_probe/l4_battle_matrix.py``):

* park the core on the story state machine's loop head ``0x0808F752``,
* write ``0x020311E6 = 0x0110`` (battle phase), ``0x020311EA = group``,
  ``0x020311ED = sub``,
* the game then runs exactly that battle.

The story route (``0x020311E6 = 0x0030``) dispatches one scene, which is
what the background / cutscene items need.

Usage
-----
    python tools/closure_battle_probe.py --battle 9:0 \
        --break 0x0809A50E --break 0x0809A368 \
        --dump 0x02000000:0x40 --hits 6 --json build/closure-probe.json
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
    Harness, hit_of, KEY_BITS, PHASE_BATTLE, PHASE_NEXT_SCENE,
    SCENE_BYTE, SUBCFG_BYTE, PHASE_WORD, MAPID_BYTE,
)


def parse_regions(spec: list[str]) -> list[tuple[int, int]]:
    out = []
    for item in spec:
        addr, _, length = item.partition(":")
        out.append((int(addr, 0), int(length or "0x40", 0)))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("rom", nargs="?", default="rom/base.gba")
    ap.add_argument("--exe", type=pathlib.Path,
                    default=REPO / "build" / "mgba-probe" / "mgba-probe.exe")
    ap.add_argument("--battle", default=None, help="group:sub")
    ap.add_argument("--scene", type=int, default=None, help="story scene id")
    ap.add_argument("--breaks", action="append", default=[],
                    help="breakpoint address (repeatable)")
    ap.add_argument("--dump", action="append", default=[],
                    help="ADDR:LENGTH memory window to record at every hit")
    ap.add_argument("--hits", type=int, default=4)
    ap.add_argument("--frames", type=int, default=900,
                    help="frames to run after the setup")
    ap.add_argument("--settle", type=int, default=120)
    ap.add_argument("--press", default="A", help="key held during the run")
    ap.add_argument("--json", type=pathlib.Path, default=None)
    ap.add_argument("--timeout", type=float, default=900.0)
    args = ap.parse_args(argv)

    if not args.exe.exists():
        print(f"ERR {args.exe} missing; run: python tools/mgba_probe/build.py",
              file=sys.stderr)
        return 2

    harness = Harness(args.exe, pathlib.Path(args.rom), timeout=args.timeout)
    regions = parse_regions(args.dump)
    record: dict = {"breaks": [int(b, 0) for b in args.breaks], "hits": []}
    try:
        if not harness.boot_to_state_machine():
            record["error"] = "could not park on the state machine loop head"
            print(json.dumps(record, indent=2))
            return 1

        if args.battle:
            group, _, sub = args.battle.partition(":")
            harness.poke(SCENE_BYTE, int(group))
            harness.poke(SUBCFG_BYTE, int(sub))
            harness.poke16(PHASE_WORD, PHASE_BATTLE)
            record["mode"] = f"battle {group}:{sub}"
        elif args.scene is not None:
            harness.poke(SCENE_BYTE, args.scene)
            harness.poke16(PHASE_WORD, PHASE_NEXT_SCENE)
            record["mode"] = f"scene {args.scene}"
        else:
            record["mode"] = "idle"

        for addr in record["breaks"]:
            harness.arm(addr)

        # let the game run; a press edge is needed every so often
        mask = KEY_BITS.get(args.press, 0)
        out = harness.send(f"frames {args.frames} {mask:#05x}")
        hit = hit_of(out)
        while hit is not None and len(record["hits"]) < args.hits:
            regs = harness.probe.registers()
            entry = {
                "address": f"0x{hit:08X}",
                "registers": {k: f"0x{v:08X}" for k, v in sorted(regs.items())},
                "memory": {},
            }
            for addr, length in regions:
                data = harness.read(addr, length)
                entry["memory"][f"0x{addr:08X}"] = data.hex()
            record["hits"].append(entry)
            print(f"hit 0x{hit:08X}: " + " ".join(
                f"{k}={v}" for k, v in sorted(regs.items()) if k in
                ("r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7")))
            harness.send("next")
            harness.rearm()
            out = harness.send(f"frames {args.frames} {mask:#05x}")
            hit = hit_of(out)
        if hit is not None:
            record["pending"] = f"0x{hit:08X}"
    finally:
        harness.close()

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8", newline="\n")
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
