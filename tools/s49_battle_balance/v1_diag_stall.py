#!/usr/bin/env python3
"""V1 (wave 16): does the stuck combat presentation ever end?

Plays the battle with the closed-loop driver until a unit is adjacent to a
bee, confirms the attack and then watches the scene for a long time.
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


def main() -> int:
    rom = REPO / "build" / "v1" / "rom-pinned.gba"
    exe = REPO / "build" / "mgba-probe-v1" / "mgba-probe.exe"
    out = REPO / "build" / "v1" / "diag" / "stall"
    out.mkdir(parents=True, exist_ok=True)
    truth = v1_truth.load(REPO / "build" / "v1" / "battle-truth.json")
    with probe_module.Probe(rom, exe=exe) as probe:
        boot = w1_boot.Boot(probe, out / "boot")
        boot.run()
        telemetry = x1_telemetry.Telemetry(probe)
        driver = v1_battle.Battle(probe, telemetry, out, verbose=False,
                                  truth=truth, allow_tools=False)
        for _ in range(400):
            values = telemetry.read()
            phase = values["phase"]
            if phase == 6 and (driver.plan or {}).get("gap") == 1:
                break
            if phase == 6:
                # the attack cannot reach yet: give the turn up
                driver.press("B", 4)
                driver.wait(24)
                continue
            if phase == 18:
                driver.advance_dialogue()
            elif phase == 23:
                driver.press("A", 4)
                driver.wait(30)
            elif phase == 1:
                driver.select_actor()
            elif phase == 3:
                driver.do_command()
            elif phase == 2:
                driver.do_move()
            else:
                driver.wait(30)
        values = telemetry.read()
        print("at-action", values["phase"], "act_index", values["action_index"])
        # walk to the punch without touching a tool entry
        for _ in range(2):
            driver.press("Down", 2)
            driver.wait(8)
        print("on-punch", telemetry.read()["action_index"])
        probe.run("frames 1 0x00000000")
        probe.run("frames 4 0x00000001")
        probe.run("frames 2 0x00000000")
        for step in range(30):
            probe.run("frames 100 0x00000000")
            values = telemetry.read()
            print(f"t={step * 100:5d} phase={values['phase']:3d} "
                  f"busy={values['presentation_busy']} "
                  f"combat_stage={values['presentation_combat_stage']} "
                  f"combat_frame={values['presentation_combat_stage_frame']} "
                  f"act_err={values['selected_action_error']} "
                  f"ctrl={values['last_control_error']} "
                  f"player={values['last_player_error']} "
                  f"scene_frame={values['scene_frame']}")
            if values["phase"] != 6:
                print("the phase moved on")
                break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
