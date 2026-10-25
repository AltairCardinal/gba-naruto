#!/usr/bin/env python3
"""Record the remake's walk with a chosen ROM and a chosen probe.

Why this tool exists
--------------------
``tools/s49_fidelity_report/capture.py`` drives the walk, but it always uses
the shared probe binary (``build/mgba-probe/mgba-probe.exe``) and it refuses to
reuse a capture whose audit does not name the requested ROM.  The C1 stream
needs two things it does not offer:

  * a **private probe** (``build/mgba-probe-w20e1/mgba-probe.exe``), because
    the shared copy is not allowed to be rebuilt and the instrument discipline
    forbids using a stale private copy;
  * the ability to record the walk **for a lane's own ROM** (the lane and the
    shared tree differ by one compiled ROM, so the "before" and "after"
    readings have to be bound to the lane's own ROM).

The environment contract is the one the lua script already uses
(``mgba_boot_input_sequence.lua``): ``Down, Down`` then thirty-two ``A``
presses, four frames held, ninety frames of settle per step.

Usage
-----
    python tools/s49_w21c1/capture_remake_walk.py \
        --rom build/w20-e1/butano-sequel/butano-sequel.gba \
        --exe build/mgba-probe-w20e1/mgba-probe.exe \
        --out-dir build/w20-e1/capture-remake-before
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
PROBE_CLIENT = REPO / "tools" / "mgba_probe" / "probe_client.py"
LUA = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano\tools\butano"
                   r"\mgba_boot_input_sequence.lua")

KEY_SEQUENCE = ["Down", "Down"] + ["A"] * 32
ZERO_INPUT_FRAMES = 240
SETTLE_FRAMES = 90
HOLD_FRAMES = 4
FRAMES_BUDGET = 3000
EXPECTED_FRAMES = 35


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rom", required=True)
    parser.add_argument("--exe", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--bios", default=None)
    args = parser.parse_args()

    rom = pathlib.Path(args.rom).resolve()
    exe = pathlib.Path(args.exe).resolve()
    out_dir = pathlib.Path(args.out_dir).resolve()
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    env["MGBA_BOOT_SEQUENCE_OUTPUT_DIR"] = str(out_dir)
    env["MGBA_BOOT_SEQUENCE_DONE_MARKER"] = str(out_dir / "done.json")
    env["MGBA_BOOT_SEQUENCE_ROM_SHA256"] = sha256_file(rom)
    env["MGBA_BOOT_SEQUENCE_KEY_SEQUENCE"] = ",".join(KEY_SEQUENCE)
    env["MGBA_BOOT_SEQUENCE_ZERO_INPUT_FRAMES"] = str(ZERO_INPUT_FRAMES)
    env["MGBA_BOOT_SEQUENCE_SETTLE_FRAMES"] = str(SETTLE_FRAMES)
    env["MGBA_BOOT_SEQUENCE_HOLD_FRAMES"] = str(HOLD_FRAMES)

    command = [sys.executable, str(PROBE_CLIENT), "--rom", str(rom),
               "--exe", str(exe)]
    if args.bios:
        command += ["--bios", str(pathlib.Path(args.bios).resolve())]
    command += ["--cmd", f"script {LUA}",
                "--cmd", f"frames {FRAMES_BUDGET} 0x000",
                "--out", str(out_dir / "result.json")]
    print("[capture] " + " ".join(command), flush=True)
    proc = subprocess.run(command, env=env, cwd=str(REPO), capture_output=True,
                          text=True, encoding="utf-8", errors="replace")
    print(proc.stdout[-2000:])
    print(proc.stderr[-2000:], file=sys.stderr)

    frames = sorted(out_dir.glob("step-*.png"))
    receipt = {
        "rom": str(rom),
        "rom_sha256": sha256_file(rom),
        "exe": str(exe),
        "exe_sha256": sha256_file(exe),
        "lua": str(LUA),
        "lua_sha256": sha256_file(LUA),
        "key_sequence": KEY_SEQUENCE,
        "zero_input_frames": ZERO_INPUT_FRAMES,
        "settle_frames": SETTLE_FRAMES,
        "hold_frames": HOLD_FRAMES,
        "exit_code": proc.returncode,
        "frame_count": len(frames),
        "expected_frame_count": EXPECTED_FRAMES,
        "frames": [frame.name for frame in frames],
    }
    with open(out_dir / "receipt.json", "w", encoding="utf-8", newline="\n") as handle:
        json.dump(receipt, handle, ensure_ascii=False, indent=1)
    print(f"[capture] frames={len(frames)}/{EXPECTED_FRAMES} exit={proc.returncode}")
    return 0 if len(frames) == EXPECTED_FRAMES else 1


if __name__ == "__main__":
    sys.exit(main())
