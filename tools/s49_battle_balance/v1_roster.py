#!/usr/bin/env python3
"""V1 (wave 16): dump the whole battle roster from the telemetry."""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import w1_boot
import w1_probe as probe_module
import x1_telemetry

REPO = HERE.parents[1]


def main() -> int:
    rom = REPO / "build" / "v1" / "rom-pinned.gba"
    exe = REPO / "build" / "mgba-probe-v1" / "mgba-probe.exe"
    out = REPO / "build" / "v1" / "diag"
    out.mkdir(parents=True, exist_ok=True)
    with probe_module.Probe(rom, exe=exe) as probe:
        boot = w1_boot.Boot(probe, out / "boot")
        boot.run()
        telemetry = x1_telemetry.Telemetry(probe)
        telemetry.locate()
        # walk out of the dialogue and the banner
        for _ in range(30):
            values = telemetry.read()
            if values["phase"] in (1, 2, 3):
                break
            probe.run("frames 1 0x00000000")
            probe.run("frames 4 0x00000001")
            probe.run("frames 2 0x00000000")
            probe.run("frames 30 0x00000000")
        values = telemetry.read()
        print("phase", values["phase"], x1_telemetry.phase_name(values["phase"]))
        print("unit_count", values["unit_count"], "active_count",
              values["active_unit_count"], "round", values["round"])
        print("slot char active  x  y hp chakra side ctrl")
        for unit in telemetry.units(values):
            index = unit["index"]
            print(f"{index:4d} {unit['character_id']:4d} {unit['active']:5d} "
                  f"{unit['x']:3d} {unit['y']:3d} {unit['hp']:3d} "
                  f"{unit['chakra']:3d} {unit['side']:4d} "
                  f"{values[f'unit_control[{index}]']:4d}")
        print("cursor", values["cursor_x"], values["cursor_y"],
              "cursor_unit_id", values["cursor_unit_id"],
              "cursor_unit_attack", values["cursor_unit_attack"],
              "cursor_unit_defense", values["cursor_unit_defense"])
        print("selected_command", values["selected_command"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
