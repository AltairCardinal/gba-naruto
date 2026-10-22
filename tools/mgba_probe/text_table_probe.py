#!/usr/bin/env python3
"""Probe the dialogue pointer table (0x08461CE8) through phase 0x0210.

`fn 0x080914D8` is the only reader-side setup for the dialogue pointer
table: the state machine's phase `0x0210` handler (0x0808F9EC) calls it with
(3, 0).  The chapter hand-off sets phase `0x0210` when the target scene is
52 (0x0808F916), but the phase can also simply be poked -- which is the
same kind of three-memory-write request the L4 battle matrix uses.

This probe therefore:
  * boots to the story state machine,
  * pokes `state[0x12] = 0x0210`,
  * presses A so the state machine dispatches that phase,
  * reports the registers at the decision point plus the table bytes.

Usage:
    python tools/mgba_probe/text_table_probe.py rom/base.gba --json build/text-table.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(r"D:\Github\gba-naruto")
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tools.mgba_probe.l4_battle_matrix import (  # noqa: E402
    Harness, hit_of, KEY_BITS, PHASE_WORD,
)

STATE = 0x020311D4
TABLE_BASE = 0x08461CE4          # the loaded constant (table proper = +4)
# The structure itself is the dialogue pointer table at 0x08461CE8; the game
# loads its base minus 4 (0x08461CE4) and then indexes from there.
TABLE_STRUCT = 0x08461CE8
DECISION = 0x080917B0            # ldr r2,[0x08461CE4]
PHASE_210 = 0x0210
SITES = {
    0x080917B0: "dialogue pointer table base load",
    0x0808F9EC: "state machine phase 0x0210 handler",
    0x0808F752: "state machine loop head",
    0x0808F916: "chapter hand-off sets phase 0x0210",
    0x0809AACC: "sound id table (control)",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("rom", nargs="?", default="rom/base.gba")
    ap.add_argument("--phase", type=int, default=PHASE_210)
    ap.add_argument("--presses", type=int, default=40)
    ap.add_argument("--json", type=pathlib.Path, default=None)
    args = ap.parse_args()

    harness = Harness(REPO / "build" / "mgba-probe" / "mgba-probe.exe",
                      pathlib.Path(args.rom))
    report = {"phase": args.phase, "hits": []}
    try:
        if not harness.boot_to_state_machine():
            print("could not park on the state machine", file=sys.stderr)
            return 2
        for addr in SITES:
            harness.arm(addr)
        harness.poke16(PHASE_WORD, args.phase)
        harness.send("next")
        for step in range(args.presses):
            out = harness.send(f"frames 8 {KEY_BITS['A']:#05x}")
            hit = hit_of(out)
            out = harness.send("frames 120 0x000")
            hit2 = hit_of(out)
            for h in (hit, hit2):
                if h is None:
                    continue
                regs = harness.probe.registers()
                state = harness.read(STATE, 0x24)
                rec = {
                    "at": f"0x{h:08X}",
                    "label": SITES.get(h, "?"),
                    "pc": f"0x{regs.get('pc', 0):08X}",
                    "r0": f"0x{regs.get('r0', 0):08X}",
                    "r1": f"0x{regs.get('r1', 0):08X}",
                    "r2": f"0x{regs.get('r2', 0):08X}",
                    "phase": f"0x{int.from_bytes(state[0x12:0x14], 'little'):04X}",
                    "scene": f"0x{state[0x16]:02X}",
                }
                if h == DECISION:
                    rec["table_dump"] = harness.read(TABLE_BASE, 48).hex(" ")
                report["hits"].append(rec)
                print(json.dumps(rec, ensure_ascii=False))
                harness.send("next")
                harness.rearm()
    finally:
        harness.close()

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
