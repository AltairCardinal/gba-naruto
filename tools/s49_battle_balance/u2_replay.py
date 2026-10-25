#!/usr/bin/env python3
"""U2 (wave 10): replay a U2 key script on the remake ROM.

Same contract as ``tools/s49_victory_capture/v4_replay.py`` (the probe's Lua
frame callback, the frame-exact PNG capture), with two additions that U2
needs:

* ``--capture step`` writes **one frame per key step** instead of every
  frame.  The full capture of a 117k frame script costs ~15 minutes and
  ~1.5 GB of PNGs; the step capture costs a fraction of that and is enough
  to answer "did the ROM reach the settlement chain?".
* the boot prefix (``--boot`` / ``--boot-a``) is configurable, because the
  remake's power-on flow (title -> briefing -> deployment -> 開始 -> party
  list) has to be walked **before** the battle script starts: otherwise the
  script's keys are consumed by the pre-battle screens and the battle never
  gets its input.

Usage::

    python tools/s49_battle_balance/u2_replay.py \\
        --script build/s49-battle-balance/u2/routeA.json \\
        --out build/s49-battle-balance/u2/step32 --capture step --boot-a 32
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
V4 = HERE.parent / "s49_victory_capture"
if str(V4) not in sys.path:
    sys.path.insert(0, str(V4))

import probe as probe_module  # noqa: E402

REPO = HERE.parents[1]
DEFAULT_EXE = REPO / "build" / "mgba-probe-u2" / "mgba-probe.exe"
DEFAULT_ROM = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\butano-sequel.gba")
LUA_SCRIPT = V4 / "capture_victory_frames.lua"


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def build_sequence(script: dict, boot: str, boot_a: int,
                   boot_hold: int = 4) -> list[str]:
    tokens: list[str] = []
    for token in boot.split(","):
        token = token.strip()
        if token:
            tokens.append(token)
    # The boot prefix walks the remake's power-on flow (title -> briefing ->
    # deployment -> 開始 -> party list).  A *held* A is what the remake treats
    # as "advance quickly"; a 4 frame tap is not enough to leave the
    # deployment screen.
    tokens.extend([f"A:90:{boot_hold}"] * boot_a)
    for step in script.get("steps", []):
        key = step.get("key", "")
        settle = int(step.get("settle", 90))
        hold = int(step.get("hold", 4))
        if key == "":
            tokens.append(f":{settle}")
        else:
            tokens.append(f"{key}:{settle}:{hold}")
    return tokens


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--script", type=pathlib.Path, required=True)
    parser.add_argument("--rom", type=pathlib.Path, default=DEFAULT_ROM)
    parser.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--capture", choices=("all", "step"), default="all")
    parser.add_argument("--boot", default="Down,Down")
    parser.add_argument("--boot-a", type=int, default=0)
    parser.add_argument("--boot-hold", type=int, default=4)
    parser.add_argument("--zero-frames", type=int, default=240)
    parser.add_argument("--frames", type=int, default=0)
    args = parser.parse_args(argv)

    script = json.loads(args.script.read_text(encoding="utf-8"))
    tokens = build_sequence(script, args.boot, args.boot_a, args.boot_hold)
    sequence_text = ",".join(tokens)

    out = args.out
    frames_dir = out / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for stale in frames_dir.glob("frame-*.png"):
        stale.unlink()

    total = args.frames
    if total <= 0:
        budget = 0
        for token in tokens:
            parts = token.split(":")
            if len(parts) >= 3 and parts[0]:
                budget += int(parts[1]) + int(parts[2]) + 4
            elif len(parts) == 2 and parts[0]:
                budget += int(parts[1]) + 8
            elif len(parts) == 2:
                budget += int(parts[1])
            else:
                budget += 98
        total = args.zero_frames + budget + 1200

    environment = {
        "MGBA_W4_OUTPUT_DIR": str(frames_dir),
        "MGBA_W4_KEY_SEQUENCE": sequence_text,
        "MGBA_W4_ZERO_FRAMES": str(args.zero_frames),
        "MGBA_W4_HOLD_FRAMES": "4",
        "MGBA_W4_SETTLE_FRAMES": "90",
        "MGBA_W4_CAPTURE": args.capture,
        "MGBA_W4_INPUT_STATE": "",
        "MGBA_W4_STATE_FILE": str(out / "state.csv"),
    }
    previous = {name: os.environ.get(name) for name in environment}
    os.environ.update(environment)
    stderr_tail: list[str] = []
    try:
        with probe_module.Probe(args.rom, exe=args.exe) as probe:
            probe.run(f"script {LUA_SCRIPT}")
            probe.frames(total, 0)
            stderr_tail = probe.stderr[-8:]
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    captured = sorted(frames_dir.glob("frame-*.png"))
    receipt = {
        "schema": "konoha.s49-u2-replay.v1",
        "rom": str(args.rom),
        "rom_sha256": sha256_file(args.rom),
        "script": str(args.script),
        "script_sha256": sha256_file(args.script),
        "script_final_phase": script.get("final_phase"),
        "capture": args.capture,
        "boot": args.boot,
        "boot_a": args.boot_a,
        "zero_frames": args.zero_frames,
        "tokens": len(tokens),
        "frames_run": total,
        "frames_captured": len(captured),
        "first_frame": captured[0].name if captured else None,
        "last_frame": captured[-1].name if captured else None,
        "probe_stderr": stderr_tail,
    }
    (out / "replay.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    print(json.dumps(receipt, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
