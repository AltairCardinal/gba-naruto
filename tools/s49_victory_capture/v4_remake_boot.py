#!/usr/bin/env python3
"""Boot the **remake** ROM and record every frame of a key sequence.

Stream V4 (wave 9).  This is the remake-side counterpart of
``w4_play.py``: that driver plays the *original* S49 battle 14 to a
decision, this one drives the *remake* (``butano-sequel.gba``) so the
settlement chain can be recorded and compared against the original's
truth frames.

The recording side is the same idea as stream W4's: a Lua frame callback
inside the probe process writes one PNG per frame, so the picture and the
frame number can never drift apart.  The Lua script is
``capture_victory_frames.lua`` (this directory owns it).

Usage::

    python tools/s49_victory_capture/v4_remake_boot.py \
        --out build/s49-victory-capture/v4/remake-boot \
        --keys "Down,Down,A,A*32"

Key token syntax (the same as the Lua script): ``"A"`` or ``"A:90"`` for a
per-key settle in frames.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import probe as probe_module  # noqa: E402

REPO = HERE.parents[1]
DEFAULT_EXE = REPO / "build" / "mgba-probe-v4" / "mgba-probe.exe"
DEFAULT_ROM = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\butano-sequel.gba")
LUA_SCRIPT = HERE / "capture_victory_frames.lua"


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def expand_keys(spec: str) -> list[str]:
    """``"Down,Down,A,A*32"`` -> ``["Down","Down","A","A", ...]``."""
    keys: list[str] = []
    for token in spec.split(","):
        token = token.strip()
        if not token:
            continue
        if "*" in token:
            name, _, count = token.partition("*")
            keys.extend([name.strip()] * int(count))
        else:
            keys.append(token)
    return keys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rom", type=pathlib.Path, default=DEFAULT_ROM)
    parser.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    parser.add_argument("--out", type=pathlib.Path,
                        default=REPO / "build" / "s49-victory-capture" / "v4"
                        / "remake-boot")
    parser.add_argument("--keys", default="Down,Down,A,A*32")
    parser.add_argument("--zero-frames", type=int, default=0)
    parser.add_argument("--hold-frames", type=int, default=4)
    parser.add_argument("--settle-frames", type=int, default=90)
    parser.add_argument("--frames", type=int, default=0,
                        help="frames to run (0 = derive from the schedule)")
    parser.add_argument("--capture", default="all", choices=["all", "step"])
    args = parser.parse_args(argv)

    out = args.out
    frames_dir = out / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for stale in frames_dir.glob("frame-*.png"):
        stale.unlink()

    keys = expand_keys(args.keys)
    sequence_text = ",".join(keys)
    total = args.frames
    if total <= 0:
        total = args.zero_frames + len(keys) * (args.hold_frames + 2
                                                 + args.settle_frames)
        total += args.settle_frames + 60

    environment = {
        "MGBA_W4_OUTPUT_DIR": str(frames_dir),
        "MGBA_W4_KEY_SEQUENCE": sequence_text,
        "MGBA_W4_ZERO_FRAMES": str(args.zero_frames),
        "MGBA_W4_HOLD_FRAMES": str(args.hold_frames),
        "MGBA_W4_SETTLE_FRAMES": str(args.settle_frames),
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
        "schema": "konoha.s49-remake-boot.v1",
        "rom": str(args.rom),
        "rom_sha256": sha256_file(args.rom),
        "keys": keys,
        "zero_frames": args.zero_frames,
        "hold_frames": args.hold_frames,
        "settle_frames": args.settle_frames,
        "frames_run": total,
        "capture_mode": args.capture,
        "frames_captured": len(captured),
        "first_frame": captured[0].name if captured else None,
        "last_frame": captured[-1].name if captured else None,
        "probe_stderr": stderr_tail,
    }
    (out / "capture.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    print(json.dumps(receipt, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
