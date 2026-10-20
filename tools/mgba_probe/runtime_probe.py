#!/usr/bin/env python3
"""Runtime evidence collector for the headless mGBA probe.

What this tool is for
---------------------
The completion ladder (`notes/runtime-verification-gates-20260710.md`) asks
for *dynamic* evidence: a breakpoint that fired, a register read at that
moment, a value the game wrote.  The mGBA CLI debugger already provides
everything needed, but two details are easy to get wrong:

1. **The fast path never checks breakpoints.**  `core->runFrame()` is a
   plain frame step; only `mDebuggerRunFrame()` consults the breakpoint
   table.  The probe's `frames` / `run` commands therefore use the fast
   path when no breakpoint is armed and the debugger path otherwise, so a
   key press and a breakpoint hit can happen in the same window.

2. **A breakpoint that fired stops the core there.**  The breakpoint stays
   armed, so the next `cont` immediately reports the *same* address again
   and the game never moves.  The fix is the cycle
   `delete <id>` -> `next` (step past the instruction) -> `b <addr>` again.

The probe also exposes mGBA's own key state in WRAM, so the tool can report
what the *game* saw rather than what the harness intended:

    0x0300000C  u16  keys currently held   (bit set = pressed)
    0x0300000E  u16  keys newly pressed this frame
    0x030009F0  u16  previous frame's held mask (history)

Usage:
    python tools/mgba_probe/runtime_probe.py rom/base.gba --press START --press A
    python tools/mgba_probe/runtime_probe.py rom/base.gba \
        --breakpoint 0x080977B8 --press A --json build/runtime-trace.json
    python tools/mgba_probe/runtime_probe.py rom/base.gba --watch 0x0300067C
"""
from __future__ import annotations

import argparse
import json
import pathlib
import queue
import subprocess
import sys
import threading
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
DEFAULT_EXE = REPO / "build" / "mgba-probe" / "mgba-probe.exe"

KEYS_HELD = 0x0300000C
KEYS_NEW = 0x0300000E
KEYS_HISTORY = 0x030009F0

KEY_BITS = {
    "A": 0x001, "B": 0x002, "SELECT": 0x004, "START": 0x008,
    "RIGHT": 0x010, "LEFT": 0x020, "UP": 0x040, "DOWN": 0x080,
}

REGS = [f"r{i}" for i in range(16)] + ["sp", "lr"]


def parse_status(lines: dict) -> dict:
    """Parse mGBA's `status` output.

    mGBA prints `r0: 00000001   r1: FFFFFFFF ...` -- the register name
    carries the colon and the value is the *next* token.
    """
    out: dict[str, int] = {}
    tokens: list[str] = []
    for line in lines:
        tokens.extend(line.replace("cpsr:", " cpsr: ").split())
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
                out[name] = int(tokens[j], 16)
            except ValueError:
                continue
            break
    return out


class Probe:
    """A live probe process with a command/response protocol."""

    def __init__(self, exe: pathlib.Path, rom: pathlib.Path, timeout: float = 300.0):
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

    def u16(self, address: int) -> int:
        raw = self.read_bytes(address, 2)
        return int.from_bytes(raw[:2], "little") if len(raw) >= 2 else 0

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
            # The debugger may be left paused on a breakpoint; the CLI's
            # `quit` then never reaches the main loop.  Do not hang.
            self.proc.kill()
            try:
                self.proc.wait(timeout=5)
            except Exception:
                pass


def arm_breakpoint(probe: Probe, address: int) -> int | None:
    for line in probe.send(f"b {address:#x}"):
        if "breakpoint #" in line:
            return int(line.split("#")[1].split()[0])
    return None


def arm_watchpoint(probe: Probe, address: int) -> int | None:
    for line in probe.send(f"watch/w {address:#x}"):
        if "watchpoint #" in line:
            return int(line.split("#")[1].split()[0])
    return None


def frames_done(out: list[str]) -> int:
    """Frames the host actually executed (the loop stops early on a hit)."""
    for line in out:
        if "done=" in line:
            try:
                return int(line.rsplit("done=", 1)[1].split()[0])
            except (IndexError, ValueError):
                pass
    return 0


def key_state(probe: Probe) -> dict:
    held = probe.u16(KEYS_HELD)
    new = probe.u16(KEYS_NEW)
    history = probe.u16(KEYS_HISTORY)
    return {
        "held": held,
        "held_mask": f"0x{held:04X}",
        "new": new,
        "new_mask": f"0x{new:04X}",
        "history_mask": f"0x{history:04X}",
        "pressed_now": [name for name, bit in KEY_BITS.items() if held & bit],
        "pressed_new": [name for name, bit in KEY_BITS.items() if new & bit],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rom", type=pathlib.Path)
    ap.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    ap.add_argument("--boot-frames", type=int, default=1500)
    ap.add_argument("--press", action="append", default=[],
                    metavar="KEY[:FRAMES]",
                    help="press a key (A/B/START/SELECT/UP/DOWN/LEFT/RIGHT), "
                         "optionally ':FRAMES' frames long; repeatable")
    ap.add_argument("--settle-frames", type=int, default=60)
    ap.add_argument("--breakpoint", action="append", type=lambda v: int(v, 0),
                    default=[], help="ARM address to break on; repeatable")
    ap.add_argument("--watch", action="append", type=lambda v: int(v, 0),
                    default=[], help="address to watch for writes; repeatable")
    ap.add_argument("--json", type=pathlib.Path, default=None)
    args = ap.parse_args()

    if not args.exe.exists():
        print(f"ERR {args.exe} missing; run: python tools/mgba_probe/build.py",
              file=sys.stderr)
        return 2

    probe = Probe(args.exe, args.rom)
    trace: list[dict] = []
    breakpoints: dict[int, int] = {}   # address -> breakpoint id
    watchpoints: dict[int, int] = {}
    try:
        probe.send(f"frames {args.boot_frames} 0x000")
        trace.append({"step": "boot", "state": key_state(probe)})
        for address in args.breakpoint:
            ident = arm_breakpoint(probe, address)
            if ident is not None:
                breakpoints[address] = ident
        for address in args.watch:
            ident = arm_watchpoint(probe, address)
            if ident is not None:
                watchpoints[address] = ident

        for index, spec in enumerate(args.press):
            name, _, frames_text = spec.partition(":")
            key = name.strip().upper()
            if key not in KEY_BITS:
                print(f"ERR unknown key {name!r}", file=sys.stderr)
                return 2
            frames = int(frames_text) if frames_text else 8
            out = probe.send(f"frames {frames} {KEY_BITS[key]:#05x}")
            regs = parse_status(probe.send("status"))
            bp_hit = any("Hit breakpoint" in line for line in out)
            wp_hit = any("Hit watchpoint" in line for line in out)
            entry = {
                "step": f"press:{key}",
                "frames_requested": frames,
                "frames_done": frames_done(out),
                "breakpoint_hit": bp_hit,
                "watchpoint_hit": wp_hit,
                "state": key_state(probe),
                "registers": {k: f"0x{v:08X}" for k, v in sorted(regs.items())},
            }
            if bp_hit or wp_hit:
                entry["pc"] = f"0x{regs.get('r15', 0):08X}"
                entry["lr"] = f"0x{regs.get('lr', 0):08X}"
                # The core is stopped on the breakpoint.  Disarm it, step
                # past the instruction and re-arm, otherwise the next run
                # reports the same address forever.
                #
                # NOTE: mGBA's `delete` only removes *breakpoints*; a
                # watchpoint id is NOT cleared by it (ARMDebuggerClearBreakpoint
                # only walks the breakpoint list).  Re-arming a watchpoint
                # would therefore pile up duplicates, so watchpoints are
                # never re-armed here -- they just stay armed and the core
                # is stepped past the offending store.
                for address, ident in list(breakpoints.items()):
                    probe.send(f"delete {ident}")
                    breakpoints[address] = arm_breakpoint(probe, address) or 0
                # No `next`: when a breakpoint fires, the CPU is already
                # parked on the *following* instruction (mGBA compares
                # `gprs[PC] - instructionLength` with the breakpoint
                # address), so the hit instruction has already run and the
                # program counter does not need to be stepped.
            trace.append(entry)
            if args.settle_frames:
                probe.send(f"frames {args.settle_frames} 0x000")
    finally:
        probe.close()

    report = {"rom": str(args.rom), "trace": trace}
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8", newline="\n")

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for row in trace:
        state = row.get("state", {})
        line = f"{row['step']:14s} held={state.get('held_mask', '-')} " \
               f"new={state.get('new_mask', '-')}"
        if "frames_done" in row:
            line += f"  frames={row['frames_done']}/{row['frames_requested']}"
        if row.get("breakpoint_hit"):
            line += f"  BREAKPOINT pc={row.get('pc')} lr={row.get('lr')}"
        if row.get("watchpoint_hit"):
            line += f"  WATCHPOINT pc={row.get('pc')}"
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
