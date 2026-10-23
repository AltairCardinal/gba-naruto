#!/usr/bin/env python3
"""在断点处把「说话人名表读取」的全链条读出来（第十八轮调试用）。

用法：
    python tools/mgba_probe/speaker_read_trace.py build/speaker-test.gba 0x08097A12

在断点处打印：
  * r1（解引用前的地址）
  * 槽里的 4 字节（该条目的指针）
  * 解引用后指向的那串字（按字库解码）

依据：notes/evidence/speaker-name-table-20261023.md
"""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from tools.mgba_probe.story_vm_capture import Probe, KEY_BITS  # noqa: E402
from tools import text_codec  # noqa: E402


def main() -> int:
    rom = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "build/speaker-test.gba")
    bp = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x08097A12
    mapping, _ = text_codec.load_mapping(None)

    probe = Probe(REPO / "build" / "mgba-probe" / "mgba-probe.exe", rom)
    try:
        probe.send("frames 1500 0x000")
        ident = None
        for line in probe.send(f"b {bp:#x}"):
            if "breakpoint #" in line:
                ident = int(line.split("#")[1].split()[0])
        print(f"断点 {bp:#x} 已下（id={ident}）")
        for i, key in enumerate(["START", "A", "A", "A", "A", "A", "A"]):
            out = probe.send(f"frames 90 0x{KEY_BITS[key]:03X}")
            hit = any("Hit breakpoint" in line for line in out)
            if not hit:
                print(f"[{i}] {key}: 未命中")
                continue
            regs = probe.registers()
            r1 = regs.get("r1", 0)
            r0 = regs.get("r0", 0)
            r7 = regs.get("r7", 0)
            slot = probe.read_bytes(r1, 4)
            pointer = int.from_bytes(slot, "little") if len(slot) == 4 else 0
            raw = probe.read_bytes(pointer, 32) if pointer else b""
            text = ""
            for j in range(0, len(raw) - 1, 2):
                code = (raw[j] << 8) | raw[j + 1]
                if code == 0:
                    break
                text += mapping.get(code, f"{{{code:04X}}}")
            print(f"[{i}] {key}: r7=0x{r7:08X} r0=0x{r0:08X} r1=0x{r1:08X} "
                  f"槽={slot.hex()} → 0x{pointer:08X} 「{text}」")
            for address in list(armed):
                probe.send(f"delete {armed[address]}")
                armed[address] = arm(probe, address)
            probe.send("frames 6 0x000")
            probe.send("frame")
    finally:
        probe.close()
    return 0


def arm(probe, address):
    for line in probe.send(f"b {address:#x}"):
        if "breakpoint #" in line:
            return int(line.split("#")[1].split()[0])
    return 0


armed = {}

if __name__ == "__main__":
    raise SystemExit(main())
