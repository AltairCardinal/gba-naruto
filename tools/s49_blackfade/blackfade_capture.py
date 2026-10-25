#!/usr/bin/env python3
"""Run the frame-by-frame Lua capture in the probe and keep the receipt.

The Lua script (``capture_frames.lua``) runs *inside* the emulator process, so
one screenshot per frame costs a PNG encode instead of a pipe round trip.
That is what makes a frame-exact black-field measurement affordable.

Usage::

    python tools/s49_blackfade/blackfade_capture.py \
        --out build/s49-blackfade/original-entry \
        --state "D:\\...\\scenario-49-battle-14-entry.ss9" \
        --keys "A*20" --settle 90 --frames 2100
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
VICTORY = REPO / "tools" / "s49_victory_capture"
for path in (str(HERE), str(VICTORY)):
    if path not in sys.path:
        sys.path.insert(0, path)

import probe as probe_module  # noqa: E402

DEFAULT_EXE = REPO / "build" / "mgba-probe-w3" / "mgba-probe.exe"
DEFAULT_ROM = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano\rom\base.gba")
DEFAULT_STATE = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\artifacts\runtime-checkpoints"
    r"\scenario-49-battle-14-entry.ss9")
LUA_SCRIPT = HERE / "capture_frames.lua"


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expand_keys(spec: str) -> list[str]:
    """``"Down,Down,A,A*3"`` -> ``["Down","Down","A","A","A","A"]``."""
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
    parser.add_argument("--out", type=pathlib.Path,
                        default=REPO / "build" / "s49-blackfade" / "capture")
    parser.add_argument("--rom", type=pathlib.Path, default=DEFAULT_ROM)
    parser.add_argument("--state", type=pathlib.Path, default=DEFAULT_STATE,
                        help="savestate to load first (use --no-state to boot)")
    parser.add_argument("--no-state", action="store_true")
    parser.add_argument("--keys", default="",
                        help="key sequence, e.g. 'A*20' or 'Down,Down,A,A*10'")
    parser.add_argument("--zero-frames", type=int, default=0)
    parser.add_argument("--hold-frames", type=int, default=4)
    parser.add_argument("--settle-frames", type=int, default=90)
    parser.add_argument("--frames", type=int, default=0,
                        help="frames to run (0 = derive from the schedule)")
    parser.add_argument("--capture", default="all", choices=["all", "step"])
    parser.add_argument("--key-log", type=pathlib.Path, default=None,
                        help="a play.json with a key_log: replay it frame "
                             "exactly (the per key settle is kept)")
    parser.add_argument("--max-keys", type=int, default=0,
                        help="replay only the first N keys of the log")
    parser.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    args = parser.parse_args(argv)

    out = args.out
    frames_dir = out / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    if args.key_log:
        document = json.loads(args.key_log.read_text(encoding="utf-8"))
        entries = document.get("key_log") or []
        if args.max_keys:
            entries = entries[:args.max_keys]
        keys = [entry["key"] for entry in entries]
        schedule = [f"{entry['key']}:{entry['settle']}" for entry in entries]
        sequence_text = ",".join(schedule)
        hold_frames = entries[0]["hold"] if entries else args.hold_frames
        release_frames = entries[0]["release"] if entries else args.release_frames
        zero_frames = 0
    else:
        keys = expand_keys(args.keys)
        sequence_text = ",".join(keys)
        hold_frames = args.hold_frames
        release_frames = args.release_frames
        zero_frames = args.zero_frames
    total = args.frames
    if total <= 0:
        total = zero_frames + len(keys) * (hold_frames + release_frames
                                           + args.settle_frames)
        total += args.settle_frames + 60

    environment = {
        "MGBA_W3_OUTPUT_DIR": str(frames_dir),
        "MGBA_W3_KEY_SEQUENCE": sequence_text,
        "MGBA_W3_ZERO_FRAMES": str(zero_frames),
        "MGBA_W3_HOLD_FRAMES": str(hold_frames),
        "MGBA_W3_SETTLE_FRAMES": str(args.settle_frames),
        "MGBA_W3_CAPTURE": args.capture,
        "MGBA_W3_INPUT_STATE": "" if args.no_state else str(args.state),
    }
    # the probe subprocess inherits this process' environment, and the Lua
    # script reads its configuration from there
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
        "schema": "konoha.s49-blackfade-capture.v1",
        "rom": str(args.rom),
        "rom_sha256": sha256_file(args.rom),
        "state": None if args.no_state else str(args.state),
        "state_sha256": None if args.no_state else sha256_file(args.state),
        "keys": keys,
        "key_log": str(args.key_log) if args.key_log else None,
        "zero_frames": zero_frames,
        "hold_frames": hold_frames,
        "release_frames": release_frames,
        "settle_frames": args.settle_frames,
        "frames_run": total,
        "capture_mode": args.capture,
        "frames_captured": len(captured),
        "first_frame": captured[0].name if captured else None,
        "last_frame": captured[-1].name if captured else None,
        "probe_stderr": stderr_tail,
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "capture.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    print(json.dumps(receipt, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
