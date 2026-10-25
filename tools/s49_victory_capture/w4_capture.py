#!/usr/bin/env python3
"""Frame-exact capture of the original ROM's battle (stream W4 instrument).

The Lua companion (``capture_victory_frames.lua``) runs **inside** the emulator
process.  Its frame callback writes, for every single frame:

* the rendered frame as a PNG, and
* the live battle state (HP of all nine slots, cursor, menu level, menu
  cursor, the action-tail block, every unit's live cell) as one CSV row.

Because both come from the same callback, the picture and the state words
always describe the same frame.  The four previous attempts at the original
victory screen (K -> M -> W3 -> X3) all died on "which screen am I on?"
guesses; here the recording side never guesses.

Usage::

    python tools/s49_victory_capture/w4_capture.py \
        --state "<...>/scenario-49-battle-14-turn4-two-kills.ss9" \
        --keys "A,A,Down:60" --frames 900 \
        --out build/s49-victory-capture/w4/run1
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
DEFAULT_EXE = REPO / "build" / "mgba-probe-w4" / "mgba-probe.exe"
DEFAULT_ROM = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano\rom\base.gba")
DEFAULT_STATE = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\artifacts\runtime-checkpoints"
    r"\scenario-49-battle-14-turn4-two-kills.ss9")
LUA_SCRIPT = HERE / "capture_victory_frames.lua"


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    parser.add_argument("--state", type=pathlib.Path, default=DEFAULT_STATE)
    parser.add_argument("--rom", type=pathlib.Path, default=DEFAULT_ROM)
    parser.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    parser.add_argument("--out", type=pathlib.Path,
                        default=REPO / "build" / "s49-victory-capture" / "w4" / "capture")
    parser.add_argument("--keys", default="", help="key sequence, e.g. 'A*20'")
    parser.add_argument("--zero-frames", type=int, default=0)
    parser.add_argument("--hold-frames", type=int, default=4)
    parser.add_argument("--settle-frames", type=int, default=90)
    parser.add_argument("--frames", type=int, default=0,
                        help="frames to run (0 = derive from the schedule)")
    parser.add_argument("--capture", default="all", choices=["all", "step"])
    parser.add_argument("--no-manifest", action="store_true",
                        help="skip the per frame sha256 manifest")
    args = parser.parse_args(argv)

    out = args.out
    frames_dir = out / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    state_csv = out / "state.csv"

    keys = expand_keys(args.keys)
    sequence_text = ",".join(keys)
    total = args.frames
    if total <= 0:
        total = args.zero_frames + len(keys) * (args.hold_frames + args.settle_frames)
        total += args.settle_frames + 60

    environment = {
        "MGBA_W4_OUTPUT_DIR": str(frames_dir),
        "MGBA_W4_KEY_SEQUENCE": sequence_text,
        "MGBA_W4_ZERO_FRAMES": str(args.zero_frames),
        "MGBA_W4_HOLD_FRAMES": str(args.hold_frames),
        "MGBA_W4_SETTLE_FRAMES": str(args.settle_frames),
        "MGBA_W4_CAPTURE": args.capture,
        "MGBA_W4_INPUT_STATE": str(args.state),
        "MGBA_W4_STATE_FILE": str(state_csv),
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
    manifest_path = out / "frames.sha256"
    if not args.no_manifest and captured:
        lines = []
        for path in captured:
            lines.append(f"{sha256_file(path)}  {path.name}")
        manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    receipt = {
        "schema": "konoha.s49-victory-capture-w4.v1",
        "rom": str(args.rom),
        "rom_sha256": sha256_file(args.rom),
        "state": str(args.state),
        "state_sha256": sha256_file(args.state),
        "keys": keys,
        "key_sequence": sequence_text,
        "zero_frames": args.zero_frames,
        "hold_frames": args.hold_frames,
        "settle_frames": args.settle_frames,
        "frames_run": total,
        "capture_mode": args.capture,
        "frames_captured": len(captured),
        "first_frame": captured[0].name if captured else None,
        "last_frame": captured[-1].name if captured else None,
        "state_csv": str(state_csv),
        "frames_manifest": None if args.no_manifest else str(manifest_path),
        "probe_stderr": stderr_tail,
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "capture.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    print(json.dumps({key: receipt[key] for key in (
        "frames_run", "frames_captured", "first_frame", "last_frame")},
        ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
