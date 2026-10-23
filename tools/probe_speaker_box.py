#!/usr/bin/env python3
"""Read-only dynamic probe: dump the message-box object right after op 0x08
rendered the name, so we can see the name's tiles written into the box
tilemap (obj + 0x1E) with no intermediate byte buffer.

0x08097A4A is reached after `bl 0x806626c` (the renderer) but before the
portrait helper; r6 is the message-box object pointer (callee-saved).
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
BP = 0x08097A4A


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    probe = Probe(EXE, ROM)
    armed = {}
    try:
        probe.send("frames 1200 0x000")
        armed[BP] = arm(probe, BP) or 0
        plan = ["START"] + ["A"] * 40
        done = 0
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
            box = regs.get("r6", 0)
            hdr = probe.read_bytes(box, 0x20)
            width = int.from_bytes(hdr[8:10], "little")
            height = int.from_bytes(hdr[0x0A:0x0C], "little")
            tiles = probe.read_bytes(box + 0x1E, 0x100)
            print("step=%d  box(obj)=0x%08X  width=%d height=%d" % (step, box, width, height))
            for row in range(4):
                seg = tiles[row * width * 2:(row + 1) * width * 2]
                if not seg:
                    break
                vals = [int.from_bytes(seg[i:i + 2], "little") for i in range(0, len(seg), 2)]
                print("   row%d: %s" % (row, " ".join("%04X" % v for v in vals)))
            done += 1
            probe.send("delete %d" % armed[BP])
            armed[BP] = arm(probe, BP) or 0
            probe.send("frames 6 0x000")
            probe.send("frame")
            if done >= 2:
                break
    finally:
        probe.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())