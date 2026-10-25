#!/usr/bin/env python3
"""Capture one original-game state: BG2 tilemap, VRAM and the IO registers.

The four exported overlay moments (field / movegrid / grid16 / banner) never
use the original's green ``hatch_shift`` family, so the family priority
between "legal target" (green) and "move reachable" (cyan) cannot be settled
from them.  The original's *target selection* state can: it is the state where
the green family is drawn.

This script loads an original savestate and reads the three regions the
overlay analysis needs, each one frame after the same state, so they always
describe the same frame:

    BG2 tilemap   0x06001000, 2048 bytes   (32x32 entries, screen space)
    VRAM          0x06000000, 0x18000 bytes
    IO registers  0x04000000, 0x400 bytes

Usage::

    python tools/s49_w1/capture_original_state.py \
        --state D:/Shell/Github/gba-naruto-butano/artifacts/runtime-checkpoints/scenario-41-target-select.ss9 \
        --out build/s49-w1/original-target-select
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
PROBE_CLIENT = REPO / "tools" / "mgba_probe" / "probe_client.py"

DEFAULT_EXE = REPO / "build" / "mgba-probe-w1" / "mgba-probe.exe"
DEFAULT_ROM = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano\rom\base.gba")

BG2_TILEMAP_ADDR = 0x06001000
BG2_TILEMAP_LEN = 2048
VRAM_ADDR = 0x06000000
VRAM_LEN = 0x18000
IO_ADDR = 0x04000000
IO_LEN = 0x400


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--state", type=pathlib.Path, required=True)
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    ap.add_argument("--rom", type=pathlib.Path, default=DEFAULT_ROM)
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    regions = (
        ("bg2", BG2_TILEMAP_ADDR, BG2_TILEMAP_LEN),
        ("vram", VRAM_ADDR, VRAM_LEN),
        ("io", IO_ADDR, IO_LEN),
    )
    commands: list[str] = []
    for name, address, length in regions:
        # Reload the state before every region so all three describe the same
        # frame: `framedump` advances the emulator by one frame.
        commands.append(f"load {args.state}")
        commands.append(
            f"framedump 1 0x{address:08X} {length} 0x000 {args.out / name}")

    argv = [sys.executable, str(PROBE_CLIENT), "--exe", str(args.exe),
            "--rom", str(args.rom)]
    for command in commands:
        argv += ["--cmd", command]
    argv += ["--out", str(args.out / "probe.json")]
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=900)
    document = json.loads((args.out / "probe.json").read_text(encoding="utf-8"))
    bad = [step for step in document["steps"] if step["status"] != "ok"]
    if bad:
        print(f"ERR probe step failed: {bad[0]['command']}: {bad[0]['output']}")
        return 1
    for name, _address, length in regions:
        path = args.out / f"{name}-0000.bin"
        if not path.is_file() or path.stat().st_size != length:
            print(f"ERR {path} is missing or has the wrong size")
            return 1
    print(f"wrote {args.out}/bg2-0000.bin, vram-0000.bin, io-0000.bin")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
