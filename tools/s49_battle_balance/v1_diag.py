#!/usr/bin/env python3
"""V1 (wave 16): dump the battle telemetry around the boot, phase by phase."""
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
        print("boot:", boot.run())
        telemetry = x1_telemetry.Telemetry(probe)
        print("telemetry at", hex(telemetry.locate(verbose=True)))
        for step in range(60):
            values = telemetry.read()
            print(f"step {step:3d} phase={values['phase']:3d} "
                  f"{x1_telemetry.phase_name(values['phase']):24s} "
                  f"round={values['round']} cursor=({values['cursor_x']},"
                  f"{values['cursor_y']}) cursor_unit={values['cursor_unit_id']} "
                  f"units={values['unit_count']} busy={values['presentation_busy']} "
                  f"ctrl_err={values['last_control_error']} "
                  f"player_err={values['last_player_error']}")
            if values["phase"] == 18:
                # tap A to advance the dialogue
                probe.run("frames 1 0x00000000")
                probe.run("frames 4 0x00000001")
                probe.run("frames 2 0x00000000")
                probe.run("frames 30 0x00000000")
            else:
                probe.run("frames 1 0x00000000")
                probe.run("frames 4 0x00000001")
                probe.run("frames 2 0x00000000")
                probe.run("frames 30 0x00000000")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
