#!/usr/bin/env python3
"""Z1 (wave 14): find out why the closed-loop driver stalls in a dialogue.

Y1's ``y1_play.py`` replays U2's route and drives the two live decisions
(action list, target cell) from the ROM's own telemetry.  On the current ROM it
walks into round 2 and then stops with::

    step 57 (A, phase 18): the dialogue never advanced
    script_phase=1 (wait_for_input) command_index=2 selector=2
    message_window_visible=1 presentation_busy=0

The scene only turns a held A into a script confirmation when **all** of the
following hold (``battle_runtime_scene.cpp``)::

    script_waiting_for_input = ! presentation.busy()
                             && state.phase == script_blocked
                             && state.script.phase == wait_for_input;
    if(! state.script.typewriter_active &&
        ! script_confirmation_latched &&
        bn::keypad::a_held()) { ... controller.confirm(); }

The telemetry does not expose ``typewriter_active``, so this tool answers the
question empirically:

* it samples the screen every few frames -- if the picture changes, something
  is still animating (the typewriter or a presentation); if it is frozen, the
  scene is idle and the input path itself is broken;
* it then tries four **different press patterns** and reports which one (if
  any) moves the script fingerprint.

The tool saves a savestate at the stall point, so every later experiment can
start from the same state instead of replaying the whole battle.

Usage::

    python tools/s49_battle_balance/z1_dialogue_probe.py \\
        --rom build/s49-package-y4-final/work/pinned-rom/measured.gba \\
        --route build/s49-battle-balance/u2/routeY.json \\
        --out build/z1/dialogue
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import w1_boot  # noqa: E402
import w1_probe as probe_module  # noqa: E402
import x1_telemetry  # noqa: E402
import y1_play  # noqa: E402

KEY_A = 0x001

WATCH_FIELDS = (
    "phase", "round", "current_side", "selected_unit", "unit_count",
    "action_count", "action_index", "selected_action_id", "selected_action_error",
    "cursor_x", "cursor_y", "presentation_busy", "map_movement_active",
    "map_movement_sequence", "condition_outcome", "script_phase",
    "script_selector", "script_command_index", "script_text_address",
    "script_message_window_visible", "scene_frame",
)


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


class DialogProbe(y1_play.Driver):
    """A driver that stops at the first stall and diagnoses it."""

    def __init__(self, *args, diagnose_call: int = 4, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.diagnosis: dict[str, object] = {}
        self.diagnosed = False
        self.calls = 0
        self.diagnose_call = diagnose_call

    # ------------------------------------------------------------- sampling
    def telemetry_view(self) -> dict[str, int]:
        values = self.state()
        return {name: values[name] for name in WATCH_FIELDS}

    def screen_is_moving(self, samples: int = 8, gap: int = 16) -> dict:
        """Are the frames changing?  (the typewriter / a presentation would)"""
        digests = []
        paths = []
        for index in range(samples):
            path = self.out / "diag" / f"still-{index:02d}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            self.probe.run(f"shot {path}")
            digests.append(sha256_file(path))
            paths.append(path.name)
            self.wait(gap)
        unique = len(set(digests))
        return {"samples": samples, "gap_frames": gap, "distinct_screens": unique,
                "shots": paths}

    # --------------------------------------------------------------- presses
    def try_pattern(self, name: str, before: tuple) -> dict:
        """One press pattern; report whether the script moved."""
        self.probe.run("keyoff")
        self.wait(8)
        if name == "tap6":
            self.probe.run(f"frames 6 0x{KEY_A:08X}")
            self.probe.run(f"frames 6 0x{0:08X}")
        elif name == "hold240":
            self.probe.run(f"key 0x{KEY_A:08X}")
            self.probe.run("run 240")
            self.probe.run("keyoff")
        elif name == "frames240":
            self.probe.run(f"frames 240 0x{KEY_A:08X}")
        elif name == "tap5x":
            for _ in range(5):
                self.probe.run(f"frames 6 0x{KEY_A:08X}")
                self.probe.run(f"frames 16 0x{0:08X}")
        else:
            raise KeyError(name)
        after = self.script_fingerprint(self.state())
        values = self.state()
        shot = self.shot(f"after-{name}")
        return {
            "pattern": name,
            "fingerprint_before": list(before),
            "fingerprint_after": list(after),
            "script_advanced": list(after) != list(before),
            "phase": values["phase"],
            "phase_name": x1_telemetry.phase_name(values["phase"]),
            "script_phase": values["script_phase"],
            "script_command_index": values["script_command_index"],
            "script_text_address": values["script_text_address"],
            "presentation_busy": values["presentation_busy"],
            "map_movement_active": values["map_movement_active"],
            "shot": shot.name,
        }

    # ---------------------------------------------------------- the override
    def press_until(self, key, predicate, max_frames: int = 900,
                    poll: int = 4) -> bool:
        self.calls += 1
        if self.diagnosed or self.calls != self.diagnose_call:
            return super().press_until(key, predicate, max_frames, poll)
        self.diagnosed = True
        values = self.state()
        before = self.script_fingerprint(values)
        report: dict[str, object] = {
            "call_index": self.calls,
            "at_frame": self.frames,
            "telemetry": self.telemetry_view(),
            "fingerprint": list(before),
            "moving": self.screen_is_moving(),
            "patterns": [],
        }
        # The first pattern only: if it works the stall is gone.
        result = self.try_pattern("tap6", before)
        report["patterns"].append(result)
        if not result["script_advanced"]:
            before = tuple(result["fingerprint_after"])
            for name in ("hold240", "frames240", "tap5x"):
                result = self.try_pattern(name, before)
                report["patterns"].append(result)
                if result["script_advanced"]:
                    break
                before = tuple(result["fingerprint_after"])
        report["telemetry_after"] = self.telemetry_view()
        self.diagnosis = report
        (self.out / "diagnosis.json").write_text(
            json.dumps(report, indent=1, ensure_ascii=False) + "\n",
            encoding="utf-8", newline="\n")
        self.log(f"DIAGNOSIS: {json.dumps(report, ensure_ascii=False)}")
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rom", type=pathlib.Path, required=True)
    parser.add_argument("--route", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--exe", type=pathlib.Path,
                        default=HERE.parents[1] / "build" / "mgba-probe-z1" /
                        "mgba-probe.exe")
    parser.add_argument("--state", type=pathlib.Path, default=None,
                        help="load this savestate instead of booting")
    parser.add_argument("--max-steps", type=int, default=0)
    parser.add_argument("--diagnose-call", type=int, default=4,
                        help="which press_until call to diagnose (4 = the "
                             "round-2 dialogue in routeY.json)")
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    route = json.loads(args.route.read_text(encoding="utf-8"))
    started = time.time()
    receipt: dict[str, object] = {
        "schema": "konoha.s49-z1-dialogue-probe.v1",
        "rom": str(args.rom),
        "rom_sha256": sha256_file(args.rom),
        "route": str(args.route),
        "route_sha256": sha256_file(args.route),
        "out": str(args.out),
    }
    with probe_module.Probe(args.rom, exe=args.exe) as probe:
        driver = DialogProbe(probe, x1_telemetry.Telemetry(probe), args.out,
                             diagnose_call=args.diagnose_call)
        if args.state:
            probe.load(args.state)
            driver.frames = 0
        else:
            boot = w1_boot.Boot(probe, args.out / "boot")
            receipt["boot"] = boot.run()
            boot.save(args.out / "after-boot.ss9")
        driver.telemetry.locate(verbose=True)
        reached = driver.play_route(route, args.max_steps)
        receipt["reached_settlement"] = reached
        receipt["frames_run"] = driver.frames
        receipt["keys_pressed"] = driver.keys
        receipt["errors"] = driver.errors
        receipt["diagnosis"] = driver.diagnosis
        if driver.diagnosed:
            probe.save(args.out / "stall.ss9")
            receipt["stall_state"] = str(args.out / "stall.ss9")
        (args.out / "stderr.txt").write_text("\n".join(probe.stderr) + "\n",
                                             encoding="utf-8", newline="\n")
    receipt["wall_seconds"] = round(time.time() - started, 1)
    (args.out / "probe.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    print(json.dumps({key: value for key, value in receipt.items()
                      if key != "diagnosis"},
                     ensure_ascii=False, indent=1))
    print(json.dumps(receipt.get("diagnosis", {}), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
