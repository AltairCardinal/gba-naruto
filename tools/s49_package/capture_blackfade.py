#!/usr/bin/env python3
"""Capture the black field frames of one side, with the read-only Lua script.

Why this exists
---------------
``tools/s49_blackfade/blackfade_capture.py`` cannot be run as it stands: it
reads ``args.release_frames``, an argument its own parser never defines, so it
raises ``AttributeError`` before it captures anything.  That file belongs to
another stream and must not be edited, so this script drives the **same**
read-only Lua script (``tools/s49_blackfade/capture_frames.lua``) with the
**same** environment contract (``MGBA_W3_*``) and writes the **same** receipt
shape (``capture.json``).

The capture parameters are the ones the pinned captures used, so the frames
and the receipt are comparable with the history in
``notes/s49-fidelity/W3-original-truth.md``:

===============  ==========================  =========================
side             ROM / state                 keys
===============  ==========================  =========================
original         ``rom/base.gba`` + the      ``A*20``, zero 0,
                 battle-14 savestate         hold 4, settle 90
remake           the built ``butano-sequel``  ``Down,Down,A*21``,
                 .gba, no savestate           zero 240, hold 4, settle 90
===============  ==========================  =========================

Usage::

    python tools/s49_package/capture_blackfade.py \
        --rom "D:\\Shell\\...\\butano-sequel.gba" \
        --keys "Down,Down,A*21" --zero-frames 240 --frames 2552 \
        --out build/s49-package/work/s49-blackfade/remake-entry
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import sys

HERE = pathlib.Path(os.path.abspath(__file__)).parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "tools" / "s49_victory_capture"))

from probe import Probe, ProbeError  # noqa: E402  (read-only reuse)

LUA_SCRIPT = REPO / "tools" / "s49_blackfade" / "capture_frames.lua"
# A **private** probe build of this stream; the shared
# ``build/mgba-probe/mgba-probe.exe`` belongs to another stream (never
# overwrite it -- LNK1104) and is an older revision, so it is the last resort.
DEFAULT_PROBE = REPO / "build" / "mgba-probe-z4" / "mgba-probe.exe"
FALLBACK_PROBE = REPO / "build" / "mgba-probe-x4r" / "mgba-probe.exe"
LAST_RESORT_PROBE = REPO / "build" / "mgba-probe" / "mgba-probe.exe"


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expand_keys(spec: str) -> list[str]:
    """``"Down,Down,A*21"`` -> ``["Down","Down","A", ...]``."""
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rom", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--state", type=pathlib.Path, default=None)
    parser.add_argument("--keys", default="")
    parser.add_argument("--zero-frames", type=int, default=0)
    parser.add_argument("--hold-frames", type=int, default=4)
    parser.add_argument("--settle-frames", type=int, default=90)
    parser.add_argument("--frames", type=int, default=0)
    parser.add_argument("--probe", type=pathlib.Path, default=None)
    args = parser.parse_args()

    if not args.rom.is_file():
        print(f"ERR rom missing: {args.rom}", file=sys.stderr)
        return 2
    if not LUA_SCRIPT.is_file():
        print(f"ERR the Lua capture script is missing: {LUA_SCRIPT}",
              file=sys.stderr)
        return 2
    probe_exe = args.probe
    if probe_exe is None:
        for candidate in (DEFAULT_PROBE, FALLBACK_PROBE, LAST_RESORT_PROBE):
            if candidate.is_file():
                probe_exe = candidate
                break
        else:
            probe_exe = DEFAULT_PROBE
    if not probe_exe.is_file():
        print(f"ERR probe missing: {probe_exe}", file=sys.stderr)
        return 2

    out = args.out
    frames_dir = out / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for stale in frames_dir.glob("frame-*.png"):
        stale.unlink()

    keys = expand_keys(args.keys)
    total = args.frames
    if total <= 0:
        total = (args.zero_frames
                 + len(keys) * (args.hold_frames + 1 + args.settle_frames)
                 + args.settle_frames + 60)

    environment = {
        "MGBA_W3_OUTPUT_DIR": str(frames_dir),
        "MGBA_W3_KEY_SEQUENCE": ",".join(keys),
        "MGBA_W3_ZERO_FRAMES": str(args.zero_frames),
        "MGBA_W3_HOLD_FRAMES": str(args.hold_frames),
        "MGBA_W3_SETTLE_FRAMES": str(args.settle_frames),
        "MGBA_W3_CAPTURE": "all",
        "MGBA_W3_INPUT_STATE": "" if args.state is None else str(args.state),
    }
    previous = {name: os.environ.get(name) for name in environment}
    os.environ.update(environment)
    stderr_tail: list[str] = []
    try:
        with Probe(args.rom, exe=probe_exe, timeout=300.0) as device:
            device.run(f"script {LUA_SCRIPT}")
            device.frames(total, 0)
            stderr_tail = device.stderr[-8:]
    except ProbeError as error:
        print(f"ERR the probe failed: {error}", file=sys.stderr)
        return 1
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
        "state": None if args.state is None else str(args.state),
        "state_sha256": None if args.state is None else sha256_file(args.state),
        "keys": keys,
        "key_log": None,
        "zero_frames": args.zero_frames,
        "hold_frames": args.hold_frames,
        "release_frames": 1,
        "settle_frames": args.settle_frames,
        "frames_run": total,
        "capture_mode": "all",
        "frames_captured": len(captured),
        "first_frame": captured[0].name if captured else None,
        "last_frame": captured[-1].name if captured else None,
        "probe": str(probe_exe),
        "probe_sha256": sha256_file(probe_exe),
        "captured_by": "tools/s49_package/capture_blackfade.py",
        "probe_stderr": stderr_tail,
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "capture.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8", newline="\n")
    print(json.dumps({k: receipt[k] for k in
                      ("rom_sha256", "frames_run", "frames_captured",
                       "first_frame", "last_frame")}, ensure_ascii=False))
    print("->", out / "capture.json")
    if not captured:
        print("ERR no frame was captured", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
