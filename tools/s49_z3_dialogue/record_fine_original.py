"""Record the original's dialogue window at one frame per capture.

The semantic walk recorder samples every four frames; the dialogue timings
(the advance press and the first glyph of the next line) need a frame exact
measurement, so this recorder captures **every** frame of a frame window and
writes no savestate.

    python tools/s49_z3_dialogue/record_fine_original.py \
        --out build/s49-z3/fine-original --from 1100 --to 1800
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
LUA = REPO / "tools" / "s49_z3_dialogue" / "lua" / "record_fine.lua"
PROBE_CLIENT = REPO / "tools" / "mgba_probe" / "probe_client.py"
PROBE_EXE = REPO / "build" / "mgba-probe" / "mgba-probe.exe"

ORIGINAL_ROM = r"D:\Shell\Github\gba-naruto-butano\rom\base.gba"
ORIGINAL_STATE = (r"D:\Shell\Github\gba-naruto-butano\artifacts\runtime-checkpoints"
                  r"\scenario-49-battle-14-entry.ss9")

# The semantic script of the pairing walk: 24 confirm presses.
BEATS = 24
ZERO_INPUT_FRAMES = 90
HOLD_FRAMES = 4
SETTLE_FRAMES = 90


def record(out_dir: pathlib.Path, capture_from: int, capture_to: int,
           exe: pathlib.Path) -> dict:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    done_marker = out_dir / "done.json"
    env = dict(os.environ)
    env.update({
        "X2_OUTPUT_DIR": str(out_dir),
        "X2_DONE_MARKER": str(done_marker),
        "X2_KEY_SEQUENCE": ",".join(["A"] * BEATS),
        "X2_ZERO_INPUT_FRAMES": str(ZERO_INPUT_FRAMES),
        "X2_SETTLE_FRAMES": str(SETTLE_FRAMES),
        "X2_HOLD_FRAMES": str(HOLD_FRAMES),
        "X2_CAPTURE_FROM": str(capture_from),
        "X2_CAPTURE_TO": str(capture_to),
        "X2_INPUT_STATE": ORIGINAL_STATE,
    })
    command = [sys.executable, str(PROBE_CLIENT), "--rom", ORIGINAL_ROM,
               "--exe", str(exe),
               "--cmd", f"script {LUA}",
               "--cmd", f"frames {capture_to + 600} 0x000",
               "--out", str(out_dir / "probe.json")]
    proc = subprocess.run(command, env=env, cwd=str(REPO),
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    frames = sorted(out_dir.glob("step-*.png"))
    receipt = {
        "capture_from": capture_from,
        "capture_to": capture_to,
        "zero_input_frames": ZERO_INPUT_FRAMES,
        "hold_frames": HOLD_FRAMES,
        "settle_frames": SETTLE_FRAMES,
        "beats": BEATS,
        "frames": len(frames),
        "exit_code": proc.returncode,
        "stderr_tail": (proc.stderr or "").splitlines()[-8:],
    }
    (out_dir / "receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8", newline="\n")
    return receipt


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=pathlib.Path,
                    default=REPO / "build" / "s49-z3" / "fine-original")
    ap.add_argument("--from", dest="capture_from", type=int, default=1100)
    ap.add_argument("--to", dest="capture_to", type=int, default=1800)
    ap.add_argument("--exe", type=pathlib.Path, default=PROBE_EXE)
    args = ap.parse_args(argv)
    receipt = record(args.out, args.capture_from, args.capture_to, args.exe)
    print(json.dumps(receipt, ensure_ascii=False, indent=1))
    return 0 if receipt["frames"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
