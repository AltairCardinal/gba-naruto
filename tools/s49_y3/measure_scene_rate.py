#!/usr/bin/env python3
"""Measure how many emulated frames one battle scene iteration takes.

Why this exists
---------------
The remake's black field is one star mask level per *scene iteration*, but the
original's black field is one level per *two GBA frames*.  The remake's
``battle_black_field_timing`` therefore assumes "one scene frame is two GBA
frames" (see game/tests/test_battle_black_field.cpp: ``gba_frames_per_scene_frame
== 2``).

The measured capture disagrees: the remake holds every star mask level for
about four captured frames while the original holds it for two.  Two
explanations are possible:

* the scene iteration really is two GBA frames and the star mask's per level
  rebuild makes the game miss VBlanks (Butano's ``bn::core`` counts a missed
  frame in ``data.missed_frames``), or
* the scene iteration is four GBA frames to begin with.

This instrument answers that question directly: it replays the pinned capture
schedule and dumps ``konoha_battle_runtime_telemetry.scene_frame`` (the
per-iteration counter the battle and deployment scenes both write) after
*every* emulated frame.  The ratio between the captured frame index and the
scene frame counter is the number of emulated frames per iteration.

Usage::

    python tools/s49_y3/measure_scene_rate.py \
        --rom "D:\\Shell\\...\\butano-sequel.gba" \
        --out build/s49-y3/scene-rate
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

HERE = pathlib.Path(os.path.abspath(__file__)).parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "tools" / "s49_victory_capture"))

from probe import Probe, ProbeError  # noqa: E402  (read-only reuse)

# ``konoha_battle_runtime_telemetry`` (an extern "C" global in EWRAM).
#
# The address comes from the built ELF:
#   arm-none-eabi-nm butano-sequel.elf | grep konoha_battle_runtime_telemetry
#     02025ee8 B konoha_battle_runtime_telemetry
#
# The struct's fields are uint32 and ``scene_frame`` is the twelfth one
# (magic, battle_id, phase, round, current_side, selected_unit,
# active_unit_count, unit_count, selected_command, player_completed,
# enemy_completed, scene_frame), so its offset is 11 * 4 = 44.
TELEMETRY_ADDRESS = 0x02025EE8
SCENE_FRAME_OFFSET = 44
DUMP_ADDRESS = TELEMETRY_ADDRESS + SCENE_FRAME_OFFSET
DUMP_LENGTH = 16

# The pinned capture schedule of tools/s49_package/capture_blackfade.py:
# zero frames, then Down, Down and 21 A presses, each held for 4 frames with
# a 90 frame settle.
ZERO_FRAMES = 240
HOLD_FRAMES = 4
SETTLE_FRAMES = 90
KEYS = ["Down", "Down"] + ["A"] * 21

KEY_MASKS = {"A": 0x001, "Down": 0x080}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rom", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--probe", type=pathlib.Path, default=None)
    args = parser.parse_args(argv)

    probe_exe = args.probe
    if probe_exe is None:
        probe_exe = REPO / "build" / "mgba-probe-y3" / "mgba-probe.exe"
    if not probe_exe.is_file():
        print(f"ERR probe missing: {probe_exe}", file=sys.stderr)
        return 2
    if not args.rom.is_file():
        print(f"ERR rom missing: {args.rom}", file=sys.stderr)
        return 2

    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    for stale in out.glob("frame-*.bin"):
        stale.unlink()

    segments: list[tuple[int, int, str]] = []
    index = 0

    def add(count: int, mask: int, name: str) -> None:
        nonlocal index
        prefix = str(out / f"frame-{index:05d}")
        segments.append((count, mask, prefix))
        index += count

    add(ZERO_FRAMES, 0, "zero")
    for key in KEYS:
        add(HOLD_FRAMES, KEY_MASKS[key], f"hold-{key}")
        add(SETTLE_FRAMES, 0, "settle")

    samples: list[dict] = []
    try:
        with Probe(args.rom, exe=probe_exe, timeout=900.0) as device:
            for count, mask, prefix in segments:
                device.framedump(count, DUMP_ADDRESS, DUMP_LENGTH, mask, prefix)
                for step in range(count):
                    path = pathlib.Path(f"{prefix}-{step:04d}.bin")
                    raw = path.read_bytes()
                    scene_frame = int.from_bytes(raw[0:4], "little")
                    samples.append({"frame": len(samples) + 1,
                                     "scene_frame": scene_frame})
    except ProbeError as error:
        print(f"ERR the probe failed: {error}", file=sys.stderr)
        return 1

    # The per-iteration counter: how many emulated frames pass between two
    # scene frame increments.
    steps: list[dict] = []
    for before, after in zip(samples, samples[1:]):
        if after["scene_frame"] != before["scene_frame"]:
            steps.append({"frame": after["frame"],
                          "delta": after["scene_frame"] - before["scene_frame"],
                          "scene_frame": after["scene_frame"]})

    document = {
        "schema": "konoha.s49-y3-scene-rate.v1",
        "rom": str(args.rom),
        "telemetry_address": TELEMETRY_ADDRESS,
        "dump_address": DUMP_ADDRESS,
        "samples": len(samples),
        "scene_frame_first": samples[0]["scene_frame"] if samples else None,
        "scene_frame_last": samples[-1]["scene_frame"] if samples else None,
        "steps": steps,
    }
    (out / "scene-rate.json").write_text(
        json.dumps(document, indent=1) + "\n", encoding="utf-8", newline="\n")
    (out / "scene-frame.txt").write_text(
        "".join(f"{item['frame']} {item['scene_frame']}\n" for item in samples),
        encoding="utf-8", newline="\n")

    print(f"{len(samples)} emulated frames, "
          f"{len(steps)} scene frame increments, "
          f"scene_frame {document['scene_frame_first']} .. "
          f"{document['scene_frame_last']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
