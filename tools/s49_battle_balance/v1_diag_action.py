#!/usr/bin/env python3
"""V1 (wave 16): why is the action confirmation swallowed?

Walks the battle to the action selection with the closed-loop driver and then
watches the scene frame by frame while the confirm button is pressed.
"""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import w1_boot
import w1_probe as probe_module
import x1_telemetry
import v1_battle
import v1_truth

REPO = HERE.parents[1]

KEYS = {"A": 0x001, "B": 0x002, "Down": 0x080, "Right": 0x010}


def show(values, label):
    print(f"{label:12s} phase={values['phase']:3d} "
          f"{x1_telemetry.phase_name(values['phase']):22s} "
          f"busy={values['presentation_busy']} "
          f"combat_stage={values['presentation_combat_stage']} "
          f"combat_frame={values['presentation_combat_stage_frame']} "
          f"impact={values['presentation_combat_impact_index']} "
          f"act_index={values['action_index']} "
          f"act_id={values['selected_action_id']} "
          f"act_err={values['selected_action_error']} "
          f"ctrl={values['last_control_error']} "
          f"player={values['last_player_error']} "
          f"scene_frame={values['scene_frame']}")


def main() -> int:
    rom = REPO / "build" / "v1" / "rom-pinned.gba"
    exe = REPO / "build" / "mgba-probe-v1" / "mgba-probe.exe"
    out = REPO / "build" / "v1" / "diag"
    out.mkdir(parents=True, exist_ok=True)
    truth = v1_truth.load(REPO / "build" / "v1" / "battle-truth.json")
    with probe_module.Probe(rom, exe=exe) as probe:
        boot = w1_boot.Boot(probe, out / "boot")
        boot.run()
        telemetry = x1_telemetry.Telemetry(probe)
        driver = v1_battle.Battle(probe, telemetry, out, verbose=False,
                                  truth=truth)
        # walk to the action selection
        for _ in range(40):
            values = telemetry.read()
            if values["phase"] == 6:
                break
            if values["phase"] == 18:
                driver.advance_dialogue()
            elif values["phase"] == 23:
                driver.press("A", 4)
                driver.wait(30)
                driver.settle()
            elif values["phase"] == 1:
                driver.select_actor()
            elif values["phase"] == 3:
                driver.do_command()
            elif values["phase"] == 2:
                driver.do_move()
            else:
                driver.wait(30)
        show(telemetry.read(), "at-action")
        # mimic the driver: scan the list, walk back to the tool entry
        count = telemetry.read()["action_count"]
        for step in range(count):
            show(telemetry.read(), f"scan{step}")
            if step + 1 < count:
                driver.press("Down", 2)
                driver.wait(8)
        for step in range(4):
            driver.press("Down", 2)
            driver.wait(8)
        show(telemetry.read(), "walked-back")
        # press A on the current entry and watch
        for step in range(12):
            probe.run("frames 1 0x00000000")
            probe.run("frames 4 0x00000001")
            probe.run("frames 2 0x00000000")
            probe.run("frames 10 0x00000000")
            show(telemetry.read(), f"after-A{step}")
        shot = out / "frozen.png"
        probe.run(f"shot {shot}")
        print("shot:", shot)
        print("--- probe stderr ---")
        for line in probe.stderr:
            print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
