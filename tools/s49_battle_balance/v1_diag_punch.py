#!/usr/bin/env python3
"""V1 (wave 16): does the *punch* also die when an enemy is in range?

The actor moves next to the bee (so an enemy is inside every attack's range)
and then confirms the punch (index 2) **without** the action cursor ever
resting on a ninja tool entry.
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


def show(values, label):
    print(f"{label:12s} phase={values['phase']:3d} "
          f"{x1_telemetry.phase_name(values['phase']):22s} "
          f"busy={values['presentation_busy']} "
          f"act_index={values['action_index']} "
          f"act_id={values['selected_action_id']} "
          f"act_err={values['selected_action_error']} "
          f"ctrl={values['last_control_error']} "
          f"player={values['last_player_error']} "
          f"scene_frame={values['scene_frame']}")


def main() -> int:
    rom = REPO / "build" / "v1" / "rom-pinned.gba"
    exe = REPO / "build" / "mgba-probe-v1" / "mgba-probe.exe"
    out = REPO / "build" / "v1" / "diag" / "punch"
    out.mkdir(parents=True, exist_ok=True)
    truth = v1_truth.load(REPO / "build" / "v1" / "battle-truth.json")
    with probe_module.Probe(rom, exe=exe) as probe:
        boot = w1_boot.Boot(probe, out / "boot")
        boot.run()
        telemetry = x1_telemetry.Telemetry(probe)
        driver = v1_battle.Battle(probe, telemetry, out, verbose=False,
                                  truth=truth)
        for _ in range(60):
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
        # two Down presses: index 0 -> 2 (the punch), never touching a tool
        for _ in range(2):
            driver.press("Down", 2)
            driver.wait(8)
        show(telemetry.read(), "on-punch")
        before = telemetry.read()["scene_frame"]
        for step in range(4):
            probe.run("frames 1 0x00000000")
            probe.run("frames 4 0x00000001")
            probe.run("frames 2 0x00000000")
            probe.run("frames 20 0x00000000")
            show(telemetry.read(), f"after-A{step}")
        # now the target selection: walk the cursor onto the bee and confirm
        values = telemetry.read()
        if values["phase"] == 8:
            bee = [unit for unit in driver.units(values)
                   if unit["side"] == 1 and unit["active"] and unit["hp"] > 0]
            print("bees:", [(unit["x"], unit["y"]) for unit in bee])
            goal = (bee[0]["x"], bee[0]["y"])
            driver.place_cursor(goal)
            show(telemetry.read(), "cursor-on-bee")
            for step in range(6):
                probe.run("frames 1 0x00000000")
                probe.run("frames 4 0x00000001")
                probe.run("frames 2 0x00000000")
                probe.run("frames 20 0x00000000")
                show(telemetry.read(), f"after-target{step}")
        after = telemetry.read()
        print("advanced:", after["scene_frame"] > before + 1)
        probe.run(f"shot {out / 'after.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
