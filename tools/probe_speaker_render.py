#!/usr/bin/env python3
"""Read-only dynamic probe: the text renderer is called with the name pointer.

Breakpoints:
  0x08066276  renderer entry   -> r0 = dest object, r1 = source string pointer
  0x08066726  renderer exit    -> r0 = final source cursor (points at the NUL)

Every call whose source pointer lies inside the speaker-name table is a name
render; we print start/end/length.
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
TBL_LO, TBL_HI = 0x085A57C4, 0x085A5AC4
MODE = sys.argv[1] if len(sys.argv) > 1 else "entry"
BP = 0x08066276 if MODE == "entry" else 0x08066726


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    probe = Probe(EXE, ROM)
    armed = {}
    try:
        probe.send("frames 1200 0x000")
        armed[BP] = arm(probe, BP) or 0
        rom = ROM.read_bytes()
        plan = ["START"] + ["A"] * 40
        seen = 0
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
            if step == 7 and MODE == "exit":
                for L in probe.send("status"):
                    print("  RAW| " + L)
            ptr = regs.get("r1", 0) if MODE == "entry" else regs.get("r2", 0)
            print("  [dbg] hit pc=%s r0=0x%08X r1=0x%08X r2=0x%08X r3=0x%08X sp=0x%08X" % (hex(hit), regs.get("r0",0), regs.get("r1",0), regs.get("r2",0), regs.get("r3",0), regs.get("sp",0)))
            if TBL_LO <= ptr < TBL_HI:
                off = ptr - 0x08000000
                raw = rom[off:off + 16]
                n = 0
                while n < len(raw) and raw[n] != 0:
                    n += 1
                slot = (ptr - TBL_LO) // 12
                print("[%s] step=%d  ptr=0x%08X (slot %d, +%d)  strlen=%d bytes = %d glyph codes"
                      % (MODE, step, ptr, slot, (ptr - TBL_LO) % 12, n, n // 2))
                print("     bytes: %s" % raw[:n + 1].hex(" "))
                seen += 1
            probe.send("delete %d" % armed[BP])
            armed[BP] = arm(probe, BP) or 0
            probe.send("frames 6 0x000")
            probe.send("frame")
            if seen >= 6:
                break
    finally:
        probe.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())