#!/usr/bin/env python3
"""Prove the `runtime-state` story-config field with a *natural* readout.

What this closes
----------------
``story_config[0]`` is the byte ``0x020311ED`` (``state[0x19]``).  Until
2026-10-22 it had no non-zero runtime readout: the story dispatcher
``0x0808F5C8`` copies ``state[0x18]`` into it and ``0x0808F5CC`` clears
``state[0x18]`` right afterwards, so every snapshot sees zero.

The dispatcher is not the only writer.  The story VM's opcode ``0x1F``
(``0x08097C3C``) writes the field from its own operand:

    0x08097C3C: ldr  r1, [pc, #4]     ; r1 = 0x020311D4
    0x08097C3E: ldrb r0, [r7, #1]     ; r0 = operand byte 1
    0x08097C40: strb r0, [r1, #0x19] ; state[0x19] = operand

Five scripts use it with operand **1** -- scenes 2, 3, 4, 6 and 7 -- so the
game itself puts a non-zero value into the field.  Reaching scene 2's copy
needs the story choice menu to be answered with row 1 (the VM's branch2
opcode ``0x06`` at ``0x080979D6`` reads the chosen row from
``0x0200A880``).

Readers of the same byte
------------------------
* ``0x08097E00`` -- the VM's opcode ``0x39`` (``ldrb r0,[r0,#0x19]``).
* ``0x0808F942`` -- the battle phase of the state machine, which copies the
  byte into ``ctrl[2]`` (``0x02026806``), the battle sub-config.

Usage
-----
    python tools/mgba_probe/runtime_state_probe.py rom/base.gba \\
        --scenes 2 --force-row 1 --presses 140 --trace
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from tools.mgba_probe.l4_battle_matrix import (  # noqa: E402
    Harness, hit_of, KEY_BITS, PHASE_WORD, SCENE_BYTE,
)

STATE19 = 0x020311ED
CTRL = 0x02026804
ANSWER_ADDR = 0x0200A880

# The sites that carry the evidence.
SITES = {
    0x08097C3E: "VM opcode 0x1F: reads the operand",
    0x08097C40: "VM opcode 0x1F: WRITES state[0x19]",
    0x08097E00: "VM opcode 0x39: READS state[0x19]",
    0x0808F942: "battle phase (0x0110): reads state[0x19]",
    0x0808F944: "battle phase (0x0110): writes ctrl[2]",
    0x080977B8: "SENTINEL story VM entry",
    0x0808F588: "SENTINEL story dispatcher -> map load",
    0x080960BE: "story choice menu: loads the finished flag",
}
# Extra sites that only trace how far the script got.
TRACE_SITES = {
    0x080978DC: "VM op 0x01 dialogue",
    0x08097992: "VM op 0x05 menu-text",
    0x080979D6: "VM op 0x06 branch2 (reads the answer row)",
    0x08097C9C: "VM op 0x1B music",
    0x08097C2C: "VM op 0x16 switch to the after root",
}


def pc_of(regs: dict) -> int:
    """mGBA prints r15, not `pc`."""
    return regs.get("r15", regs.get("pc", 0)) & 0xFFFFFFFF


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("rom", nargs="?", default="rom/base.gba")
    ap.add_argument("--scenes", default="2")
    ap.add_argument("--state", default="build/l2-states/sweep.ss9")
    ap.add_argument("--presses", type=int, default=140)
    ap.add_argument("--force-row", type=int, default=None)
    ap.add_argument("--trace", action="store_true")
    ap.add_argument("--json", type=pathlib.Path, default=None)
    args = ap.parse_args()

    scenes = [int(s) for s in args.scenes.split(",") if s.strip()]
    harness = Harness(REPO / "build" / "mgba-probe" / "mgba-probe.exe",
                      pathlib.Path(args.rom))
    records: list[dict] = []
    try:
        for scene in scenes:
            harness.send(f"load {args.state}")
            harness.disarm_all()
            armed = dict(SITES)
            if args.trace:
                armed.update(TRACE_SITES)
            for addr in armed:
                harness.arm(addr)
            harness.poke(SCENE_BYTE, scene)
            harness.poke16(PHASE_WORD, 0x0030)
            harness.send("next")
            for _ in range(args.presses):
                out = harness.send(f"frames 8 {KEY_BITS['A']:#05x}")
                hit = hit_of(out)
                regs = harness.probe.registers() if hit is not None else {}
                pc = pc_of(regs)
                out2 = harness.send("frames 120 0x000")
                hit2 = hit_of(out2)
                regs2 = harness.probe.registers() if hit2 is not None else {}
                pc2 = pc_of(regs2)
                for h, p, r in ((hit, pc, regs), (hit2, pc2, regs2)):
                    if h is None:
                        continue
                    if h == 0x080960BE and args.force_row is not None:
                        # the choice menu is about to be consumed; the VM's
                        # branch2 reads the chosen row from 0x0200A880
                        harness.poke(ANSWER_ADDR, args.force_row & 0xFF)
                    mem = harness.read(STATE19, 1)
                    ctrl = harness.read(CTRL, 8)
                    answer = harness.read(ANSWER_ADDR, 1)
                    records.append({
                        "scene": scene,
                        "hit": f"0x{h:08X}",
                        "pc": f"0x{p:08X}",
                        "label": {**SITES, **TRACE_SITES}.get(h, "?"),
                        "r0": f"0x{r.get('r0', 0):08X}",
                        "state19": f"0x{mem[0]:02X}" if mem else "?",
                        "answer_row": f"0x{answer[0]:02X}" if answer else "?",
                        "ctrl": ":".join(f"{b:02X}" for b in ctrl) if ctrl else "?",
                    })
                    harness.send("next")
                    harness.rearm()
    finally:
        harness.close()

    for rec in records:
        print(json.dumps(rec, ensure_ascii=False))
    labels = sorted({r["label"] for r in records})
    print(f"\nsites hit: {labels}")
    wrote = [r for r in records if r["hit"] == "0x08097C40"]
    print(f"non-zero story_config[0] readouts: "
          f"{[r['state19'] for r in wrote]}")
    if args.json:
        from tools.lib.io import write_json
        write_json(args.json, {"records": records})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
