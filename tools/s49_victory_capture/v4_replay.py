#!/usr/bin/env python3
"""Replay a generated key script on the **remake** ROM and record every frame.

Stream V4 (wave 9).  ``v4_route_gen.cpp`` derives the key script from the
remake's own controller (offline, deterministic); this tool replays those
keys on the ROM through the probe's Lua frame callback, so the settlement
chain is recorded frame exactly -- the same recording contract stream W4
used for the original.

Usage::

    python tools/s49_victory_capture/v4_replay.py \
        --script build/s49-victory-capture/v4/route.json \
        --out build/s49-victory-capture/v4/remake-settlement

``--boot`` is the key prefix that gets the ROM from power-on into the
battle (the title and the pre-battle briefing).  ``--boot-a`` is how many
extra A presses the boot needs.
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


def build_sequence(script: dict, boot: str, boot_a: int) -> list[str]:
    tokens: list[str] = []
    for token in boot.split(","):
        token = token.strip()
        if token:
            tokens.append(token)
    tokens.extend(["A"] * boot_a)
    for step in script.get("steps", []):
        key = step.get("key", "")
        settle = int(step.get("settle", 90))
        hold = int(step.get("hold", 4))
        if key == "":
            tokens.append(f":{settle}")
        else:
            tokens.append(f"{key}:{settle}:{hold}")
    return tokens


def build_spam(cycles: int, settle: int, tail: int,
               tail_settle: int, boot: str = "",
               boot_a: int = 0,
               cycle: str = "A,B") -> list[str]:
    """``A``/``B`` alternating, then a tail of ``A`` presses.

    The alternating pair walks the battle's state machine (confirm advances,
    cancel backs out) until the battle ends; the tail then walks the
    settlement chain, whose pages are all confirmed with ``A``.

    ``cycle`` may carry a third key: the unit-selection cursor does **not**
    advance on its own when a unit's action is cancelled, so without it the
    same unit is picked forever and the round never ends.
    """
    tokens: list[str] = []
    for token in boot.split(","):
        token = token.strip()
        if token:
            tokens.append(token)
    tokens.extend(["A"] * boot_a)
    keys = [key.strip() for key in cycle.split(",") if key.strip()]
    for _ in range(cycles):
        for key in keys:
            tokens.append(f"{key}:{settle}:4")
    for _ in range(tail):
        tokens.append(f"A:{tail_settle}:4")
    return tokens


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--script", type=pathlib.Path, required=True)
    parser.add_argument("--spam", type=int, default=0,
                        help="use the A/B spam driver with this many cycles "
                             "instead of the generated key script")
    parser.add_argument("--spam-settle", type=int, default=24)
    parser.add_argument("--spam-tail", type=int, default=30)
    parser.add_argument("--spam-tail-settle", type=int, default=240)
    parser.add_argument("--spam-cycle", default="A,B",
                        help="the key cycle of the spam driver")
    parser.add_argument("--rom", type=pathlib.Path, default=DEFAULT_ROM)
    parser.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    parser.add_argument("--out", type=pathlib.Path,
                        default=REPO / "build" / "s49-victory-capture" / "v4"
                        / "remake-settlement")
    parser.add_argument("--boot", default="Down,Down",
                        help="the key prefix that reaches the battle")
    parser.add_argument("--boot-a", type=int, default=0,
                        help="extra A presses for the boot")
    parser.add_argument("--zero-frames", type=int, default=240)
    parser.add_argument("--frames", type=int, default=0)
    args = parser.parse_args(argv)

    script = json.loads(args.script.read_text(encoding="utf-8"))
    if args.spam:
        tokens = build_spam(args.spam,
                            args.spam_settle,
                            args.spam_tail,
                            args.spam_tail_settle,
                            args.boot,
                            args.boot_a,
                            args.spam_cycle)
    else:
        tokens = build_sequence(script, args.boot, args.boot_a)
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
        "MGBA_W4_CAPTURE": "all",
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
        "schema": "konoha.s49-remake-replay.v1",
        "rom": str(args.rom),
        "rom_sha256": sha256_file(args.rom),
        "script": str(args.script),
        "script_sha256": sha256_file(args.script),
        "script_final_phase": script.get("final_phase"),
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
