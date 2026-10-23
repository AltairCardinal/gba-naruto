#!/usr/bin/env python3
"""Runtime capture of the story-VM opcode handlers and their helpers.

Why
---
`tools/story_vm_ops.py` proves the *static* meaning of every story-VM opcode
by re-reading the ROM.  For the six opcodes whose meaning lives inside a
helper (0x02 -> 0x80967E8, 0x03 -> 0x8096668, 0x04 -> 0x8096A04,
0x12 -> 0x80968EC, 0x18 -> 0x8096B34, 0x21 -> 0x8096740) the static proof
still leaves one thing open: *which operand byte becomes which field*.

This tool closes that gap with a live capture.  It breaks on the helper's
entry instruction, and at the moment of the hit it reads

  * the argument registers (r0..r3), and
  * r7, which still points at the opcode byte of the running script
    instruction (the VM handler loads the operands with `ldrb rX, [r7, #k]`
    and never touches r7 before the call), and
  * the script bytes at r7, so the opcode and its operand bytes can be read
    straight out of the running instruction stream, and
  * the message-box object the helper is about to touch
    (`0x03005E50[slot]`, a pointer table).

Because mGBA parks the CPU *after* the breakpoint instruction, and the
helpers' first instruction is `push {r4, r5, r6, r7, lr}` (which leaves
r0..r3 and r7 alone), the captured registers are exactly the arguments the
handler passed.

Usage
-----
    python tools/mgba_probe/story_vm_capture.py rom/base.gba \
        --breakpoint 0x080967E8 --json build/story-vm-capture-02.json

    # capture all six helpers in one session
    python tools/mgba_probe/story_vm_capture.py rom/base.gba \
        --breakpoint 0x080967E8 --breakpoint 0x08096668 \
        --breakpoint 0x08096A04 --breakpoint 0x080968EC \
        --breakpoint 0x08096B34 --breakpoint 0x08096740 \
        --json build/story-vm-capture-all.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import queue
import re
import subprocess
import sys
import threading
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
DEFAULT_EXE = REPO / "build" / "mgba-probe" / "mgba-probe.exe"

KEY_BITS = {
    "A": 0x001, "B": 0x002, "SELECT": 0x004, "START": 0x008,
    "RIGHT": 0x010, "LEFT": 0x020, "UP": 0x040, "DOWN": 0x080,
}

# The two message boxes live in a pointer table at 0x03005E50.
BOX_TABLE = 0x03005E50
BOX_COUNT = 2
BOX_DUMP = 0x40

REGS = [f"r{i}" for i in range(16)] + ["sp", "lr"]

HIT_RE = re.compile(r"Hit breakpoint\s+(\d+)\s+at\s+(0x[0-9A-Fa-f]+)")


class Probe:
    """A live probe process with a command/response protocol."""

    def __init__(self, exe: pathlib.Path, rom: pathlib.Path, timeout: float = 600.0):
        self.proc = subprocess.Popen(
            [str(exe), str(rom)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
        self.deadline = time.monotonic() + timeout
        self.stderr_lines: list[str] = []
        threading.Thread(target=self._drain_stderr, daemon=True).start()
        self._read_line()  # banner

    def _drain_stderr(self) -> None:
        assert self.proc.stderr is not None
        for line in self.proc.stderr:
            self.stderr_lines.append(line.rstrip("\r\n"))

    def _read_line(self) -> str | None:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("probe timed out")
        result: queue.Queue = queue.Queue()
        reader = threading.Thread(
            target=lambda: result.put(self.proc.stdout.readline()), daemon=True)
        reader.start()
        reader.join(remaining)
        if reader.is_alive():
            raise TimeoutError("probe timed out")
        line = result.get()
        return line if line else None

    def send(self, command: str) -> list[str]:
        assert self.proc.stdin is not None
        token = f"__end_{len(self.stderr_lines)}_{abs(hash(command)) % 9973}"
        self.proc.stdin.write(f"{command}\necho {token}\n")
        self.proc.stdin.flush()
        lines: list[str] = []
        while True:
            line = self._read_line()
            if line is None:
                raise EOFError("probe exited")
            line = line.rstrip("\r\n")
            if line == token:
                return lines
            lines.append(line)

    def read_bytes(self, address: int, length: int) -> bytes:
        # The host's argument parser needs the 0x prefix; without it the
        # address is mis-parsed and the read hits unmapped memory.
        out = self.send(f"dump 0x{address:08X} {length}")
        payload: list[str] = []
        for line in out:
            line = line.strip()
            if not line or line.startswith("DUMP ") or line == "ENDDUMP":
                continue
            if "Bad memory" in line:
                continue
            if all(c in "0123456789abcdefABCDEF" for c in line):
                payload.append(line)
        try:
            return bytes.fromhex("".join(payload))
        except ValueError:
            return b""

    def registers(self) -> dict[str, int]:
        out = self.send("status")
        tokens: list[str] = []
        for line in out:
            tokens.extend(line.replace("cpsr:", " cpsr: ").split())
        regs: dict[str, int] = {}
        for i, token in enumerate(tokens):
            if not token.endswith(":"):
                continue
            name = token[:-1]
            if name not in REGS:
                continue
            for j in range(i + 1, min(i + 3, len(tokens))):
                if tokens[j].endswith(":"):
                    break
                try:
                    regs[name] = int(tokens[j], 16)
                except ValueError:
                    continue
                break
        return regs

    def close(self) -> None:
        try:
            self.send("quit")
        except Exception:
            pass
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            try:
                self.proc.wait(timeout=5)
            except Exception:
                pass


def arm(probe: Probe, address: int) -> int | None:
    for line in probe.send(f"b {address:#x}"):
        if "breakpoint #" in line:
            return int(line.split("#")[1].split()[0])
    return None


def capture(probe: Probe, regs: dict[str, int], address: int, script_bytes: int = 8) -> dict:
    """Everything the capture knows about the paused state."""
    entry: dict = {
        "breakpoint": f"0x{address:08X}",
        "registers": {k: f"0x{v:08X}" for k, v in sorted(regs.items())},
    }
    script = regs.get("r7")
    if script is not None:
        raw = probe.read_bytes(script, script_bytes)
        entry["script_address"] = f"0x{script:08X}"
        entry["script_bytes"] = raw.hex(" ")
        if len(raw) >= 4:
            entry["opcode"] = f"0x{raw[0]:02X}"
            entry["operand_bytes"] = [f"0x{b:02X}" for b in raw[1:4]]
    table = probe.read_bytes(BOX_TABLE, BOX_COUNT * 4)
    boxes = []
    for i in range(BOX_COUNT):
        if len(table) < (i + 1) * 4:
            break
        ptr = int.from_bytes(table[i * 4:(i + 1) * 4], "little")
        item = {"index": i, "pointer": f"0x{ptr:08X}"}
        if ptr:
            item["bytes"] = probe.read_bytes(ptr, BOX_DUMP).hex(" ")
        boxes.append(item)
    entry["boxes"] = boxes
    return entry


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rom", type=pathlib.Path)
    ap.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    ap.add_argument("--breakpoint", action="append", type=lambda v: int(v, 0),
                    default=[], help="helper/handler entry address; repeatable")
    ap.add_argument("--boot-frames", type=int, default=1200)
    ap.add_argument("--press", action="append", default=[], metavar="KEY[:FRAMES]",
                    help="key to press after boot; repeatable")
    ap.add_argument("--plan", default=None,
                    help="compact press plan: comma separated KEY[:FRAMES] items, "
                         "where KEY*N repeats the item N times "
                         "(e.g. 'START,A:30*4,B:8*400')")
    ap.add_argument("--max-steps", type=int, default=40)
    ap.add_argument("--script-bytes", type=int, default=8,
                    help="每个命中读多少字节的脚本正文（默认 8；"
                         "要读整句正文就调大）")
    ap.add_argument("--frames-per-step", type=int, default=30)
    ap.add_argument("--gap-frames", type=int, default=6,
                    help="frames with no key pressed after a breakpoint hit; the "
                         "aborted frame leaves the game's 'new key' edge consumed, "
                         "so without a release gap the game never advances again")
    ap.add_argument("--press-gap", type=int, default=2,
                    help="frames with no key pressed after every press; the host "
                         "releases the key at the end of a `frames` window and "
                         "re-presses it at the start of the next one, so without "
                         "a gap the game never sees a second press edge")
    ap.add_argument("--frame-recover", action="store_true", default=True,
                    help="run mGBA's `frame` after a hit so the aborted frame "
                         "is finished cleanly (default on)")
    ap.add_argument("--no-frame-recover", dest="frame_recover", action="store_false")
    ap.add_argument("--json", type=pathlib.Path, default=None)
    args = ap.parse_args()

    if not args.exe.exists():
        print(f"ERR {args.exe} missing; run: python tools/mgba_probe/build.py",
              file=sys.stderr)
        return 2
    if not args.breakpoint:
        print("ERR at least one --breakpoint is required", file=sys.stderr)
        return 2

    probe = Probe(args.exe, args.rom)
    hits: list[dict] = []
    armed: dict[int, int] = {}
    try:
        probe.send(f"frames {args.boot_frames} 0x000")
        for address in args.breakpoint:
            ident = arm(probe, address)
            if ident is not None:
                armed[address] = ident

        plan = args.press or ["START", "A", "A", "A", "A"]
        if args.plan:
            plan = []
            for item in args.plan.split(","):
                item = item.strip()
                if not item:
                    continue
                name, _, count = item.partition("*")
                times = int(count) if count else 1
                plan.extend([name] * times)
        for step, spec in enumerate(plan):
            if step >= args.max_steps:
                break
            name, _, frames_text = spec.partition(":")
            key = name.strip().upper()
            if key not in KEY_BITS:
                print(f"ERR unknown key {name!r}", file=sys.stderr)
                return 2
            frames = int(frames_text) if frames_text else args.frames_per_step
            out = probe.send(f"frames {frames} 0x{KEY_BITS[key]:03X}")
            hit = None
            for line in out:
                found = HIT_RE.search(line)
                if found:
                    hit = int(found.group(2), 16)
                    break
            if hit is None:
                if args.press_gap:
                    probe.send(f"frames {args.press_gap} 0x000")
                continue
            # Read the registers *before* anything resumes the core: the
            # registers at the breakpoint are the arguments the handler
            # passed to the helper.
            regs = probe.registers()
            entry = capture(probe, regs, hit, args.script_bytes)
            entry["step"] = step
            entry["key"] = key
            hits.append(entry)
            # The core is parked on the breakpoint.  Disarm it, step past the
            # instruction and re-arm, otherwise the next run reports the same
            # address forever.
            for address, ident in list(armed.items()):
                probe.send(f"delete {ident}")
                new_id = arm(probe, address)
                armed[address] = new_id or 0
            # The aborted frame consumed the key edge: the game saw the key
            # held when the frame was cut short, so its "newly pressed" mask
            # is already set and the next press of the same key looks like
            # "still held".  Release the key for a few frames so the game can
            # see the edge again.
            if args.gap_frames:
                probe.send(f"frames {args.gap_frames} 0x000")
            # mGBA's `frame` runs the aborted frame to its next boundary, so
            # the game gets a well formed frame instead of resuming in the
            # middle of one.
            if args.frame_recover:
                probe.send("frame")
    finally:
        probe.close()

    report = {
        "rom": str(args.rom),
        "breakpoints": [f"0x{a:08X}" for a in args.breakpoint],
        "press_plan": plan,
        "hits": hits,
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8", newline="\n")

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"captured {len(hits)} hit(s)")
    for row in hits:
        print(f"  bp={row['breakpoint']} step={row['step']} key={row['key']} "
              f"script={row.get('script_address')} opcode={row.get('opcode')} "
              f"operands={row.get('operand_bytes')} "
              f"r0={row['registers'].get('r0')} r1={row['registers'].get('r1')} "
              f"r2={row['registers'].get('r2')} r3={row['registers'].get('r3')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
