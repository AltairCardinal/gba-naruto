#!/usr/bin/env python3
"""V1 (wave 16): is the action *hover* or the action *confirm* the trigger?

The driver plays until a unit stands next to a bee (the bee is then inside
the punch's range).  At the action selection the cursor is moved onto the
punch and **cancelled** with B -- no attack is made.  If the phase leaves the
action selection, the hover is harmless and the confirm is the trigger; if the
phase stays, the hover already killed the input.
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
    out = REPO / "build" / "v1" / "diag" / "hover"
    out.mkdir(parents=True, exist_ok=True)
    truth = v1_truth.load(REPO / "build" / "v1" / "battle-truth.json")
    with probe_module.Probe(rom, exe=exe) as probe:
        boot = w1_boot.Boot(probe, out / "boot")
        boot.run()
        telemetry = x1_telemetry.Telemetry(probe)
        driver = v1_battle.Battle(probe, telemetry, out, verbose=False,
                                  truth=truth, allow_tools=False)
        for _ in range(500):
            values = telemetry.read()
            phase = values["phase"]
            gap = (driver.plan or {}).get("gap")
            if phase == 6 and gap == 1:
                print("at the action selection, the bee is adjacent")
                break
            if phase == 6:
                # the attack cannot reach yet: give the turn up
                driver.press("B", 4)
                driver.wait(24)
                driver.expect = "end"
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
            elif phase == 12:
                driver.wait(30)
            else:
                driver.wait(30)
        values = telemetry.read()
        print("phase", values["phase"], "act_index", values["action_index"],
              "gap", gap)
        for _ in range(2):
            driver.press("Down", 2)
            driver.wait(8)
        values = telemetry.read()
        print("after two Down presses: phase", values["phase"],
              "act_index", values["action_index"],
              "act_id", values["selected_action_id"])
        # cancel (no attack): the phase must leave the action selection if the
        # input is still alive
        driver.press("B", 4)
        driver.wait(60)
        values = telemetry.read()
        print("after B: phase", values["phase"],
              x1_telemetry.phase_name(values["phase"]),
              "act_index", values["action_index"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
