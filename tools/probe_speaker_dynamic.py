#!/usr/bin/env python3
"""Read-only dynamic probe (no repo files are written).

Boots the ROM in the headless mGBA host, breaks on the story-VM 0x08 handler
just before it calls the text renderer, and reads the live registers so the
`id -> table entry` formula can be checked against the ROM bytes.

Breakpoints:
  0x08097A16  op 0x08, first name   (r0=id, r1=base+id*12, r4=table base)
  0x08097A32  op 0x0E, second name  (r0=id, r1=base+id*12, r4=table base)
"""
from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools" / "mgba_probe"))

from tools.mgba_probe.story_vm_capture import Probe, arm, KEY_BITS, HIT_RE  # noqa: E402

EXE = REPO / "build" / "mgba-probe" / "mgba-probe.exe"
ROM = REPO / "rom" / "base.gba"
BPS = [0x08097A16, 0x08097A32]
BASE = 0x085A57C4


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not EXE.exists():
        print("ERR missing %s" % EXE, file=sys.stderr)
        return 2
    probe = Probe(EXE, ROM)
    armed: dict[int, int] = {}
    try:
        probe.send("frames 1200 0x000")
        for a in BPS:
            armed[a] = arm(probe, a) or 0
        print("armed: %s" % {hex(k): v for k, v in armed.items()})
        rom = ROM.read_bytes()
        plan = ["START"] + ["A"] * 40
        hits = 0
        for step, key in enumerate(plan):
            out = probe.send("frames 30 0x%03X" % KEY_BITS[key])
            hit = None
            for line in out:
                m = HIT_RE.search(line)
                if m:
                    hit = int(m.group(2), 16)
                    break
            if hit is None:
                probe.send("frames 2 0x000")
                continue
            regs = probe.registers()
            r0 = regs.get("r0", 0)
            r1 = regs.get("r1", 0)
            r4 = regs.get("r4", 0)
            expected = BASE + r0 * 12
            live = probe.read_bytes(r1, 12)
            fileoff = r1 - 0x08000000
            disk = rom[fileoff:fileoff + 12] if 0 <= fileoff <= len(rom) - 12 else b""
            print("HIT step=%d bp=0x%08X  r0(id)=%d  r1=0x%08X  r4(base)=0x%08X"
                  % (step, hit, r0, r1, r4))
            print("    base + id*12 = 0x%08X   r1 = 0x%08X   %s"
                  % (expected, r1, "MATCH" if r1 == expected else "MISMATCH"))
            print("    live bytes @r1 : %s" % live.hex(" "))
            print("    ROM  bytes @r1 : %s   %s"
                  % (disk.hex(" "), "MATCH" if live == disk else "MISMATCH"))
            hits += 1
            for a, ident in list(armed.items()):
                probe.send("delete %d" % ident)
                armed[a] = arm(probe, a) or 0
            probe.send("frames 6 0x000")
            probe.send("frame")
            if hits >= 6:
                break
    finally:
        probe.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())