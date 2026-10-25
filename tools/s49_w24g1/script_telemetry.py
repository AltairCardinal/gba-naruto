#!/usr/bin/env python3
"""Read the remake's script telemetry out of the captured savestates.

Only the script related fields are printed: they are the ones the wave 23 /
F3 analysis asked for (message window visible / portrait visible / command
index) and they decide whether the empty dialogue box exists in the product
at all.
"""

from __future__ import annotations

import argparse
import pathlib
import struct
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "s49_battle_balance"))

import w1_probe as probe_module  # noqa: E402
import x1_telemetry as telemetry_module  # noqa: E402

FIELDS = (
    "step",
    "phase",
    "scene_frame",
    "script_phase",
    "script_selector",
    "script_command_index",
    "script_message_window_visible",
    "script_portrait_0_visible",
    "script_portrait_1_visible",
    "presentation_busy",
    "render_stage",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remake-dir", type=pathlib.Path, required=True)
    parser.add_argument("--rom", type=pathlib.Path, required=True)
    parser.add_argument("--exe", type=pathlib.Path, required=True)
    parser.add_argument("--steps", default="")
    args = parser.parse_args()

    states = sorted(args.remake_dir.glob("step-*.ss9"))
    if args.steps:
        wanted = {int(v) for v in args.steps.split(",")}
        states = [s for s in states
                  if int(s.name.split("-")[1]) in wanted]
    with probe_module.Probe(args.rom, exe=args.exe) as probe:
        telemetry = telemetry_module.Telemetry(probe)
        address = None
        for state in states:
            probe.load(state)
            if address is None:
                # The telemetry struct only exists once a state is loaded
                # (it lives in EWRAM), so the address can only be found
                # after the first load.
                address = telemetry.locate()
                print(f"telemetry at 0x{address:08X}")
            blob = probe.dump(address, telemetry_module.BYTE_COUNT)
            words = struct.unpack(
                f"<{telemetry_module.WORD_COUNT}I", blob)
            values = dict(zip(telemetry_module.FIELDS, words))
            row = {k: values.get(k) for k in FIELDS if k != "step"}
            row["step"] = state.name
            print(row)
    return 0


if __name__ == "__main__":
    sys.exit(main())
