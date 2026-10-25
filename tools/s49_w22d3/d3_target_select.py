#!/usr/bin/env python3
"""W22-D3: does the A button work in the remake's ``target_selection`` phase
once the cursor has actually been moved onto a target?

Background
----------
C1 (``notes/s49-fidelity/W21-C1-camera-pan.md`` §8) traced the "CANNOT
SELECT" banner to this chain:

    A  ->  controller.confirm()            battle_scene_controller.h:875
       ->  _runtime.preview_target(_cursor) battle_scene_controller.h:879
       ->  !preview.legal()                 battle_player_action_flow.h:1155
       ->  "CANNOT SELECT"                  battle_runtime_scene.cpp:9202

and noticed that the walk it had (``Down,Down,A*32``) never pressed a direction
key while the phase was ``target_selection``, so the cursor stayed on the
actor's own cell the whole time.

That was an *inference*, not a measurement.  This tool is the measurement: it
loads a savestate that is already inside ``target_selection``, presses the
direction keys one at a time, records the telemetry (phase / cursor / selected
unit / error codes) and a screenshot after every key, and finally presses A.

Usage::

    python tools/s49_w22d3/d3_target_select.py \\
        --rom  build/s49-package-w20/work/pinned-rom/measured.gba \\
        --exe  build/mgba-probe-w22d3/mgba-probe.exe \\
        --state build/s49-package-w20/work/s49-report/capture-remake/step-29-A.ss9 \\
        --out  build/w22-d3/exp1-arrows \\
        --keys Right,Right,Right,Down,A
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import struct
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "s49_battle_balance"))

import w1_probe as probe_module  # noqa: E402
import x1_telemetry as telemetry_module  # noqa: E402

KEYS = probe_module.KEYS

# The interesting telemetry columns.  ``last_control_error`` and
# ``last_player_error`` are what the banner is made of: 4 =
# battle_scene_control_error::player_flow_failed, 7 =
# battle_player_action_flow_error::action_rejected.
COLUMNS = (
    "phase", "round", "current_side", "selected_unit", "unit_count",
    "selected_command", "action_count", "action_index", "selected_action_id",
    "selected_action_error", "last_control_error", "last_player_error",
    "cursor_x", "cursor_y", "selected_unit_x", "selected_unit_y",
    "scene_frame", "presentation_busy", "map_movement_active",
    "condition_outcome", "first_active_enemy_x", "first_active_enemy_y",
)


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Session:
    """A probe with the battle telemetry wired in."""

    def __init__(self, rom: pathlib.Path, exe: pathlib.Path) -> None:
        self.probe = probe_module.Probe(rom, exe=exe)
        self.probe.start()
        self.telemetry = telemetry_module.Telemetry(self.probe)
        self.frames = 0
        self.keys = 0

    def close(self) -> None:
        self.probe.close()

    # ------------------------------------------------------------- plumbing
    def release_gap(self, frames: int = 1) -> None:
        if frames > 0:
            self.probe.run(f"frames {frames} 0x00000000")
            self.frames += frames

    def press(self, key: str, hold: int = 4) -> None:
        if key not in KEYS:
            raise KeyError(f"unknown key {key!r}")
        self.release_gap(1)
        self.probe.run(f"frames {hold} 0x{KEYS[key]:08X}")
        self.frames += hold
        self.keys += 1

    def wait(self, frames: int) -> None:
        if frames > 0:
            self.probe.run(f"frames {frames} 0x00000000")
            self.frames += frames

    def settle(self, steps: int = 120, step: int = 30) -> bool:
        """Wait until the scene is idle again (see ``v1_battle.py``)."""
        for _ in range(steps):
            values = self.telemetry.read()
            if (values["presentation_busy"] == 0 and
                    values["map_movement_active"] == 0):
                return True
            self.wait(step)
        return False

    # -------------------------------------------------------------- reading
    def state(self) -> dict[str, int]:
        return self.telemetry.read()

    def snapshot(self) -> dict[str, object]:
        values = self.state()
        row: dict[str, object] = {
            "phase_raw": values["phase"],
            "phase": telemetry_module.phase_name(values["phase"]),
            "cursor": [values["cursor_x"], values["cursor_y"]],
            "units": self.telemetry.units(values),
        }
        for name in COLUMNS:
            row[name] = values[name]
        return row

    def shot(self, path: pathlib.Path) -> str:
        self.probe.run(f"shot {path}")
        return sha256_file(path)


def parse_keys(text: str) -> list[str]:
    return [part.strip() for part in text.split(",") if part.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=pathlib.Path, required=True)
    parser.add_argument("--exe", type=pathlib.Path, required=True)
    parser.add_argument("--state", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--keys", default="Right,A",
                        help="comma separated key sequence")
    parser.add_argument("--hold", type=int, default=4)
    parser.add_argument("--gap", type=int, default=30,
                        help="frames to wait after every key")
    parser.add_argument("--label", default="exp")
    args = parser.parse_args(argv)

    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    session = Session(args.rom, args.exe)
    steps: list[dict[str, object]] = []
    try:
        session.probe.load(args.state)
        # The savestate may have been taken before the battle published its
        # telemetry, so the struct is located lazily.
        session.telemetry.locate(verbose=True)
        # A savestate restores the CPU state but not the frame buffer, so the
        # screen is only valid after the scene has drawn at least one frame.
        session.wait(4)

        baseline = session.snapshot()
        baseline_shot = out / "00-baseline.png"
        baseline_sha = session.shot(baseline_shot)
        steps.append({
            "index": 0,
            "key": None,
            "note": "baseline (loaded savestate)",
            "shot": str(baseline_shot),
            "sha256": baseline_sha,
            **baseline,
        })
        print(f"[0] baseline phase={baseline['phase']} "
              f"cursor={baseline['cursor']} "
              f"sel={baseline['selected_unit']} "
              f"ctrl_err={baseline['last_control_error']} "
              f"pl_err={baseline['last_player_error']}")

        for index, key in enumerate(parse_keys(args.keys), start=1):
            session.press(key, args.hold)
            session.wait(args.gap)
            session.settle()
            row = session.snapshot()
            shot = out / f"{index:02d}-{key}.png"
            sha = session.shot(shot)
            row.update({
                "index": index,
                "key": key,
                "shot": str(shot),
                "sha256": sha,
            })
            steps.append(row)
            print(f"[{index}] {key:6s} phase={row['phase']:<18} "
                  f"cursor={row['cursor']} "
                  f"sel={row['selected_unit']} "
                  f"ctrl_err={row['last_control_error']} "
                  f"pl_err={row['last_player_error']} "
                  f"scene_frame={row['scene_frame']}")

        document = {
            "schema": "konoha.s49-d3-target-select.v1",
            "generated_by": "tools/s49_w22d3/d3_target_select.py",
            "label": args.label,
            "rom": {
                "path": str(args.rom),
                "sha256": sha256_file(args.rom),
            },
            "exe": {
                "path": str(args.exe),
                "sha256": sha256_file(args.exe),
            },
            "state": {
                "path": str(args.state),
                "sha256": sha256_file(args.state),
            },
            "key_sequence": parse_keys(args.keys),
            "frames_run": session.frames,
            "keys_pressed": session.keys,
            "probe_commands": session.probe.commands,
            "steps": steps,
        }
        receipt = out / "receipt.json"
        receipt.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")
        print(f"wrote {receipt}")
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
