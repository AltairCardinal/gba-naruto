#!/usr/bin/env python3
"""Per frame telemetry of the remake's battle scene, over a dense window.

Why this tool exists
--------------------
The C1 stream has to find the *phase anchor* of the original's camera pan: the
original's pan starts at dense frame 38 of the ``step-20 -> step-21`` window
and the walk screenshot lands at dense frame 43, five increments into the pan.
The remake's dense replay puts its own walk screenshot at the same dense frame
43 (measured: 0 px), so the remake's pan has to start at dense frame 38 too.

"Which dense frame is 38" is a question about the *remake's* own phase
timeline, and the remake publishes it: ``battle_runtime_scene_telemetry``
carries the phase, the cursor and the movement animation state, and the probe
can dump it after every frame (``framedump``).

So this tool
  1. finds the telemetry struct in EWRAM (by its magic, because its address
     moves between builds),
  2. replays a walk window with the same input timing the dense capture uses
     (A held for four frames, then ninety settle frames) while dumping the
     telemetry after every frame,
  3. prints the per frame phase / cursor / movement state.

The dump index *i* of the settle command corresponds to the dense frame
``f(i+1)``: the dense capture takes its ``f001`` shot after 4 (hold) + 1
(settle) frames, and the settle dump *i* is taken after 4 + i + 1 frames.

Usage
-----
    python tools/s49_w21c1/telemetry_frames.py \
        --rom build/w20-e1/butano-sequel/butano-sequel.gba \
        --state build/w20-e1/capture-remake-before/step-24-A.ss9 \
        --exe build/mgba-probe-w20e1/mgba-probe.exe \
        --out-dir build/w20-e1/telemetry-remake/step-24-to-25
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import struct
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from s49_battle_balance.x1_telemetry import (  # noqa: E402
    BYTE_COUNT, FIELDS, MAGIC, PHASES, WORD_COUNT,
)

REPO = pathlib.Path(__file__).resolve().parents[2]
PROBE_CLIENT = REPO / "tools" / "mgba_probe" / "probe_client.py"

EWRAM_BASE = 0x02000000
EWRAM_SIZE = 0x00040000
HOLD_FRAMES = 4
SETTLE_FRAMES = 90
GBA_KEY_A = 0x0001


def phase_name(value: int) -> str:
    if 0 <= value < len(PHASES):
        return PHASES[value]
    return f"phase_{value}"


def run_probe(exe: str, rom: str, commands: list[str], out: str) -> dict:
    argv = [sys.executable, str(PROBE_CLIENT), "--exe", exe, "--rom", rom]
    for command in commands:
        argv += ["--cmd", command]
    argv += ["--out", out]
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=3600)
    if not os.path.isfile(out):
        raise RuntimeError(f"probe produced no output: {proc.stderr[-2000:]}")
    with open(out, encoding="utf-8") as handle:
        document = json.load(handle)
    bad = [step for step in document["steps"] if step["status"] != "ok"]
    if bad:
        raise RuntimeError(f"probe step failed: {bad[0]}")
    return document


def find_telemetry(exe: str, rom: str, state: str, out: str) -> int:
    """Locate the telemetry struct in EWRAM by its magic.

    The whole EWRAM is dumped in one probe session (one boot, many dump
    commands), because booting the probe per chunk is what makes this slow.
    """
    magic = struct.pack("<I", MAGIC)
    chunk = 0x8000
    commands = [f"load {state}"]
    for base in range(EWRAM_BASE, EWRAM_BASE + EWRAM_SIZE, chunk):
        commands.append(f"dump {base} {chunk}")
    run_probe(exe, rom, commands, out)
    with open(out, encoding="utf-8") as handle:
        document = json.load(handle)
    for step in document["steps"]:
        payload = step.get("dump")
        if not payload:
            continue
        blob = bytes.fromhex(payload["bytes"])
        offset = blob.find(magic)
        while offset >= 0:
            if offset % 4 == 0:
                return int(payload["address"], 16) + offset
            offset = blob.find(magic, offset + 1)
    raise RuntimeError("the battle telemetry struct was not found in EWRAM")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rom", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--exe", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    out_dir = pathlib.Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    address = find_telemetry(args.exe, args.rom, args.state,
                             str(out_dir / "scan.json"))
    print(f"[telemetry] struct at 0x{address:08X}")

    hold_prefix = str(out_dir / "hold")
    settle_prefix = str(out_dir / "settle")
    commands = [
        f"load {pathlib.Path(args.state).resolve()}",
        f"framedump {HOLD_FRAMES} 0x{address:08X} {BYTE_COUNT} {GBA_KEY_A} {hold_prefix}",
        f"framedump {SETTLE_FRAMES} 0x{address:08X} {BYTE_COUNT} 0 {settle_prefix}",
    ]
    run_probe(args.exe, args.rom, commands, str(out_dir / "probe.json"))

    rows = []
    for index in range(SETTLE_FRAMES):
        path = out_dir / f"settle-{index:04d}.bin"
        blob = path.read_bytes()
        words = struct.unpack(f"<{WORD_COUNT}I", blob)
        values = dict(zip(FIELDS, words))
        dense_frame = f"f{index + 1:03d}.png"
        rows.append({
            "dump_index": index,
            "dense_frame": dense_frame,
            "phase": values["phase"],
            "phase_name": phase_name(values["phase"]),
            "scene_frame": values["scene_frame"],
            "cursor_x": values["cursor_x"],
            "cursor_y": values["cursor_y"],
            "presentation_busy": values["presentation_busy"],
            "map_movement_active": values["map_movement_active"],
            "map_movement_elapsed": values["map_movement_elapsed"],
            "map_movement_offset_x": values["map_movement_offset_x"],
            "map_movement_offset_y": values["map_movement_offset_y"],
            "selected_unit": values["selected_unit"],
            "render_stage": values["render_stage"],
        })

    previous = None
    for row in rows:
        mark = "  <-- change" if previous is not None and (
            row["phase"] != previous["phase"] or
            row["map_movement_active"] != previous["map_movement_active"] or
            row["cursor_x"] != previous["cursor_x"] or
            row["cursor_y"] != previous["cursor_y"]) else ""
        print(f"{row['dense_frame']}  phase={row['phase_name']:<18} "
              f"scene_frame={row['scene_frame']:<5} cursor=({row['cursor_x']},"
              f"{row['cursor_y']}) move={row['map_movement_active']}/"
              f"{row['map_movement_elapsed']} sel_unit={row['selected_unit']}"
              f"{mark}")
        previous = row

    document = {
        "schema": "konoha.s49-w21c1-telemetry-frames.v1",
        "rom": args.rom,
        "state": args.state,
        "telemetry_address": f"0x{address:08X}",
        "hold_frames": HOLD_FRAMES,
        "settle_frames": SETTLE_FRAMES,
        "note": ("dump index i corresponds to the dense frame f(i+1): the dense "
                 "capture shoots f001 after 4 hold frames + 1 settle frame"),
        "rows": rows,
    }
    if args.out:
        out = pathlib.Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(document, handle, ensure_ascii=False, indent=1)
        print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
