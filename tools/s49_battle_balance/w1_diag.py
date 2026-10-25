#!/usr/bin/env python3
"""W1: run the probe with its stderr on disk and step the frame budget in
chunks, so a hang can be located and the probe's own log read while it is
still blocked.

Usage::

    python tools/s49_battle_balance/w1_diag.py \\
        --out build/s49-battle-balance/w1/diag \\
        --state build/s49-battle-balance/w1/boot1/dialogue1.ss9 \\
        --script build/s49-battle-balance/u2/routeA.json \\
        --chunk 500 --frames 12000
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
V4 = HERE.parent / "s49_victory_capture"
if str(V4) not in sys.path:
    sys.path.insert(0, str(V4))

REPO = HERE.parents[1]
DEFAULT_EXE = REPO / "build" / "mgba-probe-w1" / "mgba-probe.exe"
DEFAULT_ROM = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\butano-sequel.gba")
LUA_SCRIPT = V4 / "capture_victory_frames.lua"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=pathlib.Path, default=DEFAULT_ROM)
    parser.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--state", type=pathlib.Path, required=True)
    parser.add_argument("--script", type=pathlib.Path, required=True)
    parser.add_argument("--chunk", type=int, default=500)
    parser.add_argument("--frames", type=int, default=12000)
    parser.add_argument("--capture", default="step")
    args = parser.parse_args(argv)

    out = args.out
    frames_dir = out / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for stale in frames_dir.glob("frame-*.png"):
        stale.unlink()
    stderr_path = out / "probe-stderr.txt"

    script = json.loads(args.script.read_text(encoding="utf-8"))
    tokens = [f"{step.get('key','')}:{int(step.get('settle',90))}:"
              f"{int(step.get('hold',4))}" for step in script["steps"]]

    environment = dict(os.environ)
    environment.update({
        "MGBA_W4_OUTPUT_DIR": str(frames_dir),
        "MGBA_W4_KEY_SEQUENCE": ",".join(tokens),
        "MGBA_W4_ZERO_FRAMES": "240",
        "MGBA_W4_HOLD_FRAMES": "4",
        "MGBA_W4_SETTLE_FRAMES": "90",
        "MGBA_W4_CAPTURE": args.capture,
        "MGBA_W4_INPUT_STATE": "",
        "MGBA_W4_STATE_FILE": str(out / "state.csv"),
    })

    with open(stderr_path, "wb") as errlog:
        proc = subprocess.Popen([str(args.exe), str(args.rom)],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=errlog, text=True, bufsize=1,
                                env=environment)
        assert proc.stdin is not None
        proc.stdin.write(f"load {args.state}\n")
        proc.stdin.write(f"script {LUA_SCRIPT}\n")
        proc.stdin.flush()
        done = 0
        while done < args.frames:
            count = min(args.chunk, args.frames - done)
            started = time.monotonic()
            proc.stdin.write(f"frames {count} 0x00000000\n")
            proc.stdin.flush()
            line = proc.stdout.readline() if proc.stdout else ""
            elapsed = time.monotonic() - started
            done += count
            shots = len(list(frames_dir.glob("frame-*.png")))
            print(f"frames={done} shots={shots} {elapsed:7.2f}s "
                  f"reply={line.strip()!r}", flush=True)
        proc.stdin.write("quit\n")
        proc.stdin.flush()
        proc.wait(timeout=30)
    print(f"stderr -> {stderr_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
