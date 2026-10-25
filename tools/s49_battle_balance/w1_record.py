#!/usr/bin/env python3
"""W1 (wave 11): record the remake's battle + settlement chain on the ROM.

Why this tool exists
--------------------
U2 (wave 10) proved the remake's power-on flow is interactive and that the
offline key script alone cannot walk it: the script's keys are eaten by the
pre-battle screens.  This tool adds the **missing half** -- a modelled boot
prefix -- in front of the victory script, and records every frame.

Boot model (derived from the remake's own ``battle_preparation_flow`` and
``battle_deployment_flow``, both read-only):

===== ======================= ============================================
phase what the screen is      keys
===== ======================= ============================================
 1    preparation **root**    ``Down Down``  -> cursor on 开始任务
 2    开始任务吗？             ``A``         -> 是 (yes is the default)
 3    **deployment** screen    ``A`` x 9     -> confirm the 9 units
 4    开始 (start) title       ``A``         -> confirm the start
 5    black field              (no input)    -> the transition
 6    battle opening dialogue  the script's first three ``A`` presses
===== ======================= ============================================

The recorder runs the probe's Lua frame callback (the same one W4 used for the
original), so every PNG is frame exact.  The receipt carries the ROM's
sha256: the remake ROM is rebuilt by parallel streams, so a recording without
the ROM digest cannot be tied to a build.

Usage::

    python tools/s49_battle_balance/w1_record.py \\
        --out build/s49-battle-balance/w1/runA \\
        --script build/s49-battle-balance/u2/routeA.json \\
        --boot build/s49-battle-balance/w1/boot-prefix.json \\
        --capture step
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
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import w1_probe as probe_module  # noqa: E402

import w1_boot  # noqa: E402

REPO = HERE.parents[1]
DEFAULT_EXE = REPO / "build" / "mgba-probe-w1" / "mgba-probe.exe"
DEFAULT_ROM = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\butano-sequel.gba")
LUA_SCRIPT = HERE / "w1_capture.lua"


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def boot_tokens(plan: list[dict[str, object]]) -> list[str]:
    """Turn a boot plan into the Lua script's token syntax."""
    tokens: list[str] = []
    for action in plan:
        kind = str(action.get("do", "")).lower()
        if kind == "wait":
            tokens.append(f":{int(action.get('frames', 60))}")
        elif kind == "press":
            key = str(action["key"])
            hold = int(action.get("hold", 4))
            settle = int(action.get("settle", 60))
            tokens.append(f"{key}:{settle}:{hold}")
        else:
            raise ValueError(f"unsupported boot action {kind!r}")
    return tokens


def script_tokens(script: dict) -> list[str]:
    """Turn the victory key script into the Lua script's token syntax."""
    tokens: list[str] = []
    for step in script.get("steps", []):
        key = str(step.get("key", ""))
        settle = int(step.get("settle", 90))
        hold = int(step.get("hold", 4))
        tokens.append(f"{key}:{settle}:{hold}")
    return tokens


def budget_for(tokens: list[str], zero_frames: int) -> int:
    """Frames the token list needs.

    A token is ``KEY:settle:hold`` or ``:settle:hold`` (a pure wait).  Both
    forms spend ``settle`` frames, plus the hold and the probe's own
    bookkeeping.  Counting a pure wait as a flat 98 frames under-counts a
    script whose presentation waits are thousands of frames long, and the
    recording then stops before the last key steps ever fire.
    """
    total = zero_frames
    for token in tokens:
        parts = token.split(":")
        if len(parts) >= 3:
            total += int(parts[1]) + int(parts[2]) + 4
        elif len(parts) == 2:
            total += int(parts[1]) + 8
        else:
            total += 98
    return total + 1200


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rom", type=pathlib.Path, default=DEFAULT_ROM)
    parser.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--script", type=pathlib.Path, default=None,
                        help="victory key script (JSON)")
    parser.add_argument("--boot", type=pathlib.Path, default=None,
                        help="boot prefix plan (JSON list of actions)")
    parser.add_argument("--boot-auto", action="store_true",
                        help="closed-loop boot: walk the pre-battle screens "
                             "with the screen as the oracle and stop on the "
                             "battle's first dialogue page")
    parser.add_argument("--state", type=pathlib.Path, default=None,
                        help="savestate to load instead of booting")
    parser.add_argument("--boot-save", action="store_true",
                        help="also save the boot's savestate (it slows the "
                             "probe down by two orders of magnitude)")
    parser.add_argument("--capture", choices=("all", "step"), default="step")
    parser.add_argument("--capture-from", type=int, default=1,
                        help="first frame that is written (the recording "
                             "window); 1 = everything")
    parser.add_argument("--zero-frames", type=int, default=240)
    parser.add_argument("--frames", type=int, default=0,
                        help="frames to run (0 = derive from the token list)")
    parser.add_argument("--chunk", type=int, default=2000,
                        help="frames per probe command; a single long "
                             "'frames' command stalls the probe once the game "
                             "waits for input, so the budget is split")
    args = parser.parse_args(argv)

    tokens: list[str] = []
    if args.boot is not None:
        tokens.extend(boot_tokens(json.loads(args.boot.read_text(encoding="utf-8"))))
    boot_count = len(tokens)
    if args.script is not None:
        script = json.loads(args.script.read_text(encoding="utf-8"))
        tokens.extend(script_tokens(script))
    if not tokens:
        raise SystemExit("ERR nothing to do: pass --boot and/or --script")

    out = args.out
    frames_dir = out / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for stale in frames_dir.glob("frame-*.png"):
        stale.unlink()

    total = args.frames or budget_for(tokens, args.zero_frames)
    sequence_text = ",".join(tokens)

    environment = {
        "MGBA_W1_OUTPUT_DIR": str(frames_dir),
        "MGBA_W1_KEY_SEQUENCE": sequence_text,
        "MGBA_W1_ZERO_FRAMES": str(args.zero_frames),
        "MGBA_W1_HOLD_FRAMES": "4",
        "MGBA_W1_SETTLE_FRAMES": "90",
        "MGBA_W1_CAPTURE": args.capture,
        "MGBA_W1_CAPTURE_FROM": str(args.capture_from),
        "MGBA_W1_INPUT_STATE": "",
        "MGBA_W1_STATE_FILE": str(out / "state.csv"),
    }
    previous = {name: os.environ.get(name) for name in environment}
    os.environ.update(environment)
    stderr_tail: list[str] = []
    boot_info: dict[str, object] = {}
    try:
        with probe_module.Probe(args.rom, exe=args.exe) as probe:
            if args.state is not None:
                probe.run(f"load {args.state}")
                boot_info = {"mode": "state", "state": str(args.state)}
            elif args.boot_auto:
                boot = w1_boot.Boot(probe, out / "boot")
                boot_info = {"mode": "closed-loop", **boot.run()}
                if args.boot_save:
                    # The probe's "save" leaves a breakpoint armed in mGBA's
                    # debugger, and an armed breakpoint forces the probe onto
                    # the instruction-at-a-time path -- two orders of
                    # magnitude slower.  The recording does not need the
                    # savestate, so it is off by default.
                    boot_info["state"] = str(
                        boot.save(out / "boot" / "dialogue1.ss9"))
            probe.run(f"script {LUA_SCRIPT}")
            remaining = total
            while remaining > 0:
                count = min(args.chunk, remaining)
                probe.frames(count, 0)
                remaining -= count
            stderr_tail = probe.stderr[-8:]
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    captured = sorted(frames_dir.glob("frame-*.png"))
    receipt = {
        "schema": "konoha.s49-w1-record.v1",
        "rom": str(args.rom),
        "rom_sha256": sha256_file(args.rom),
        "script": str(args.script) if args.script else None,
        "script_sha256": sha256_file(args.script) if args.script else None,
        "boot": str(args.boot) if args.boot else None,
        "boot_sha256": sha256_file(args.boot) if args.boot else None,
        "boot_tokens": boot_count,
        "boot_info": boot_info,
        "script_tokens": len(tokens) - boot_count,
        "capture": args.capture,
        "capture_from": args.capture_from,
        "zero_frames": args.zero_frames,
        "frames_run": total,
        "frames_captured": len(captured),
        "first_frame": captured[0].name if captured else None,
        "last_frame": captured[-1].name if captured else None,
        "probe_stderr": stderr_tail,
    }
    (out / "record.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    print(json.dumps(receipt, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
