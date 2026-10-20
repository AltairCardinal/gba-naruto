#!/usr/bin/env python3
"""State-driven navigation in the headless mGBA probe.

The old web/WASM probe advanced the story by replaying a fixed number of key
presses.  That is exactly what `notes/runtime-verification-gates-20260710.md`
rules out: it needs "有效状态 + 有效输入" - a decision made from observed
state, not from a blind counter.

This driver keeps a live probe process and decides what to press from the
state it can read:

    0x020311EA  current scene / chapter id
    0x02026805  current battle stage (0 = not in battle)
    0x02026804  battle control block (8 bytes)

It stops when the requested condition holds, and can save the state so the
rest of the session starts from exactly that point.

Usage:
    python tools/mgba_probe/navigate.py --rom rom/base.gba
    python tools/mgba_probe/navigate.py --rom rom/base.gba --stop battle
    python tools/mgba_probe/navigate.py --rom rom/base.gba --stop scene --scene 1
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

# GBA key mask
KEY_A = 0x001
KEY_B = 0x002
KEY_SELECT = 0x004
KEY_START = 0x008
KEY_RIGHT = 0x010
KEY_LEFT = 0x020
KEY_UP = 0x040
KEY_DOWN = 0x080

ADDR_SCENE = 0x020311EA
ADDR_BATTLE_STAGE = 0x02026805
ADDR_BATTLE_CONTROL = 0x02026804
ADDR_PROGRESS = 0x020311E4


class Probe:
    """A live probe process with a command/response protocol."""

    def __init__(self, exe: pathlib.Path, rom: pathlib.Path, timeout: float = 120.0):
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
        """Run one command; return its output lines (echo sentinel removed)."""
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
        # address is mis-parsed and busRead8 hits unmapped memory.
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

    def state(self) -> dict:
        scene = self.read_bytes(ADDR_SCENE, 1)
        stage = self.read_bytes(ADDR_BATTLE_STAGE, 1)
        control = self.read_bytes(ADDR_BATTLE_CONTROL, 8)
        progress = self.read_bytes(ADDR_PROGRESS, 2)
        return {
            "scene": scene[0] if scene else None,
            "battle_stage": stage[0] if stage else None,
            "battle_control": control.hex(),
            "progress": int.from_bytes(progress, "little") if progress else None,
        }

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


def navigate(probe: Probe, stop: str, target_scene: int | None,
            max_steps: int, frames_per_step: int, trace: list[dict]) -> dict:
    """Advance the game until the stop condition holds."""
    history: list[dict] = []
    last_scene = None
    for step in range(max_steps):
        state = probe.state()
        history.append({"step": step, **state})
        if stop == "battle" and (state["battle_stage"] or 0) != 0:
            return {"reached": "battle", "steps": step, "state": state,
                    "history": history}
        if stop == "scene" and target_scene is not None and state["scene"] == target_scene:
            return {"reached": "scene", "steps": step, "state": state,
                    "history": history}
        if stop == "progress" and (state["progress"] or 0) != 0:
            return {"reached": "progress", "steps": step, "state": state,
                    "history": history}

        # Decide the input from the state we just read.
        scene = state["scene"] or 0
        if scene == 0:
            # Title / top menu: START enters the game.
            key = KEY_START
        else:
            # In a scene: A advances dialogue and confirms menus.
            key = KEY_A
        probe.send(f"frames {frames_per_step} 0x{key:03X}")
        if scene != last_scene:
            last_scene = scene
    final = probe.state()
    return {"reached": None, "steps": max_steps, "state": final, "history": history}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", default="rom/base.gba")
    ap.add_argument("--exe", default=str(DEFAULT_EXE))
    ap.add_argument("--stop", choices=("battle", "scene", "progress", "steps"),
                    default="battle")
    ap.add_argument("--scene", type=int, default=None)
    ap.add_argument("--max-steps", type=int, default=200)
    ap.add_argument("--frames-per-step", type=int, default=30)
    ap.add_argument("--save", default=None, help="save a savestate when reached")
    ap.add_argument("--out", default=None, help="write the JSON trace here")
    args = ap.parse_args()

    exe = pathlib.Path(args.exe)
    if not exe.exists():
        print(f"ERR {exe} missing; run: python tools/mgba_probe/build.py",
              file=sys.stderr)
        return 2

    probe = Probe(exe, pathlib.Path(args.rom))
    try:
        result = navigate(probe, args.stop, args.scene, args.max_steps,
                          args.frames_per_step, [])
        if args.save and result["reached"]:
            probe.send(f"save {args.save}")
        result["stderr"] = probe.stderr_lines
        if args.out:
            pathlib.Path(args.out).write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        probe.close()

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"reached: {result['reached']}  after {result['steps']} steps")
    print(f"final state: {json.dumps(result['state'], ensure_ascii=False)}")
    print()
    print("state trace (step, scene, battle_stage):")
    for row in result["history"]:
        print(f"  {row['step']:>4}  scene={row['scene']}  "
              f"battle={row['battle_stage']}  progress={row['progress']}")
    return 0 if result["reached"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
